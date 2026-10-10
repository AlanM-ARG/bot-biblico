import os
import time
from repositories.user_repository import UserRepository
from repositories.cache_audit_repository import CacheAuditRepository
from repositories.resource_repository import ResourceRepository
from services.rag_logger import RAGLogger, RAGLogEntry, ChunkInfo
from services.prompt_builder import PromptBuilder
from models.rag_response import RAGResponse
from llm.tier_router import TierRouter
from core.embeddings import get_encoder
from core.vector_db import get_chroma_client, get_collection
from services.graph_service import GraphService

class RAGService:
    def __init__(self, use_ephemeral_db=False):
        self.user_repo = UserRepository()
        self.cache_repo = CacheAuditRepository()
        self.resource_repo = ResourceRepository()
        self.encoder = get_encoder()
        self.logger = RAGLogger()
        self.prompt_builder = PromptBuilder()
        self._last_model_used = "unknown"
        self._last_tier_used = ""
        self._last_providers_attempted = []
        self._last_private_data_flag = False
        self.tier_router = TierRouter()
        self._retrieval_service = None  # Lazy loading — Cross-Encoder es pesado (~250ms)
        self.graph_service = GraphService()
        self._use_ephemeral_db = use_ephemeral_db
        
        if use_ephemeral_db:
            import chromadb
            self.db_client = chromadb.EphemeralClient()
            self.collection = self.db_client.get_or_create_collection(name="biblico_collection")
        else:
            self.collection = get_collection()
        
        # Coverage threshold (ChromaDB L2 distance — lower is more similar)
        self.min_relevance_score = float(os.getenv("RAG_MIN_SCORE", "1.5"))

    def _call_llm(self, prompt: str, module: str = "study_guide",
                  contains_private_data: bool = False) -> str:
        """
        Routes an LLM call through the TierRouter.
        
        Args:
            prompt: The full prompt to send.
            module: The calling module — determines which tier is used.
            contains_private_data: If True, excludes aggregator providers.
        """
        result = self.tier_router.route(
            prompt=prompt,
            module=module,
            temperature=0.3,
            # timeout=None lets TierRouter use dynamic timeouts per tier
            contains_private_data=contains_private_data,
        )
        
        self._last_model_used = f"{result.provider_name}/{result.model_name}" if result.provider_name else "error"
        self._last_tier_used = self.tier_router._resolve_tier_name(module)
        self._last_private_data_flag = contains_private_data or self.tier_router._is_private_module(module)
        
        if not result.success:
            return f"Error crítico: todos los proveedores del tier fallaron. Último error: {result.error}"
        return result.content

    def _populate_log_routing(self, log_entry: RAGLogEntry):
        """Populate the log entry with tier routing telemetry from the last call."""
        log_entry.tier_used = self._last_tier_used
        log_entry.providers_attempted = self._last_providers_attempted
        log_entry.private_data_flag = self._last_private_data_flag

    def _query_collection_filtered(self, query_text: str, n_results: int = 4):
        """Queries the vector DB, explicitly excluding discarded resources."""
        query_embedding = self.encoder.encode([query_text]).tolist()
        
        discarded_ids = self.resource_repo.get_discarded_resource_ids()
        
        # Filtro base: no leer nada que hayamos generado nosotros (evita Data Cannibalism)
        where_clause = {"category": {"$ne": "generado_por_ia"}}
        
        if discarded_ids:
            if len(discarded_ids) == 1:
                where_clause = {"$and": [where_clause, {"resource_id": {"$ne": discarded_ids[0]}}]}
            else:
                where_clause = {"$and": [where_clause, {"resource_id": {"$nin": discarded_ids}}]}
                
        return self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where_clause,
            include=["documents", "distances"]
        )

    def _retrieve_and_check_coverage(self, query_text: str, n_results: int = 4,
                                     log_entry: RAGLogEntry = None) -> tuple:
        """
        Recupera fragmentos de ChromaDB con filtro de descarte, registra telemetría de chunks
        y evalúa si la cobertura temática es suficiente según min_relevance_score.

        Returns:
            (context_docs, is_covered, distances)
            donde is_covered es True si hay documentos y al menos uno tiene distancia <= min_relevance_score.
        """
        results = self._query_collection_filtered(query_text, n_results=n_results)
        
        context_docs = results['documents'][0] if results.get('documents') else []
        distances = results['distances'][0] if results.get('distances') else []
        chunk_ids = results['ids'][0] if results.get('ids') else []
        
        if log_entry is not None:
            for i, doc in enumerate(context_docs):
                log_entry.chunks_retrieved.append({
                    "chunk_id": chunk_ids[i] if i < len(chunk_ids) else f"chunk_{i}",
                    "score": distances[i] if i < len(distances) else 0.0,
                    "snippet": doc[:100] + "..." if len(doc) > 100 else doc,
                })
                
        is_covered = bool(context_docs) and not all(d > self.min_relevance_score for d in distances)
        if not is_covered and log_entry is not None:
            log_entry.fallback_no_rag = True
            
        return context_docs, is_covered, distances

    def _retrieve_with_reranking(self, query_text: str, log_entry: RAGLogEntry = None,
                                 top_candidates: int = 50, final_top: int = 15) -> tuple:
        """
        Recuperación de alta precisión usando Cross-Encoder re-ranking.
        Pipeline: Bi-Encoder Top 50 → Cross-Encoder → Feedback Bandit → Top N.

        Mismo contrato que _retrieve_and_check_coverage() para compatibilidad:
        Returns:
            (context_docs, is_covered, distances)
        
        Si el RetrievalService no está disponible (ej. tests efímeros o
        modelo Cross-Encoder ausente), cae transparentemente al pipeline
        bi-encoder clásico.
        """
        # No usar re-ranking en modo efímero (tests)
        if self._use_ephemeral_db:
            return self._retrieve_and_check_coverage(
                query_text, n_results=min(final_top, 5), log_entry=log_entry
            )

        try:
            # Lazy-load del RetrievalService (carga Cross-Encoder la primera vez)
            if self._retrieval_service is None:
                from services.retrieval_service import RetrievalService
                self._retrieval_service = RetrievalService()
            
            candidates = self._retrieval_service.search_and_rerank(
                query=query_text,
                top_candidates=top_candidates,
                final_top=final_top
            )
            
            if not candidates:
                # Sin resultados del re-ranker → fallback clásico
                return self._retrieve_and_check_coverage(
                    query_text, n_results=min(final_top, 5), log_entry=log_entry
                )
            
            # Extraer docs y distancias del formato de RetrievalService
            context_docs = [c["text"] for c in candidates]
            distances = [c.get("vector_distance", 1.0) for c in candidates]
            
            # Registrar telemetría enriquecida en log_entry
            if log_entry is not None:
                for i, c in enumerate(candidates):
                    chunk_info = {
                        "chunk_id": c.get("metadata", {}).get("chunk_id", f"reranked_{i}"),
                        "score": c.get("vector_distance", 0.0),
                        "snippet": c["text"][:100] + "..." if len(c["text"]) > 100 else c["text"],
                    }
                    # Enriquecer con scores de re-ranking cuando disponibles
                    if "cross_encoder_score" in c:
                        chunk_info["cross_encoder_score"] = round(c["cross_encoder_score"], 4)
                    if "adaptive_boost" in c:
                        chunk_info["adaptive_boost"] = round(c["adaptive_boost"], 4)
                    if "final_score" in c:
                        chunk_info["final_score"] = round(c["final_score"], 4)
                    log_entry.chunks_retrieved.append(chunk_info)
            
            # Evaluar cobertura con misma lógica que el pipeline clásico
            is_covered = bool(context_docs) and not all(
                d > self.min_relevance_score for d in distances
            )
            if not is_covered and log_entry is not None:
                log_entry.fallback_no_rag = True
            
            return context_docs, is_covered, distances
            
        except Exception as e:
            # Cualquier fallo del Cross-Encoder → fallback transparente al bi-encoder
            print(f"⚠️ Re-ranking no disponible ({e}). Usando bi-encoder clásico.")
            return self._retrieve_and_check_coverage(
                query_text, n_results=min(final_top, 5), log_entry=log_entry
            )

    def _process_missing_topics(self, response: RAGResponse):
        """Registers missing topics in the database backlog."""
        if not response.missing_topics:
            return
            
        from database.connection import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        for topic in response.missing_topics:
            tema = topic.get("tema", "Desconocido")
            motivo = topic.get("motivo", "")
            tipo = topic.get("tipo", "General")
            
            cursor.execute("SELECT id FROM temas_pendientes WHERE tema_o_libro = ? AND estado = 'Pendiente'", (tema,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO temas_pendientes (tema_o_libro, motivo_necesidad, tipo_recurso_requerido)
                    VALUES (?, ?, ?)
                """, (tema, motivo, tipo))
                
        conn.commit()
        conn.close()

    def _record_interaction_and_dispatch_evaluation(
        self,
        query: str,
        response: RAGResponse,
        module: str,
        retrieved_chunks: list,
        log_entry: RAGLogEntry = None
    ) -> str:
        """
        Persiste la interacción en SQLite (rag_interactions) para trazabilidad,
        asigna interaction_id al RAGResponse y despacha la evaluación asíncrona
        de calidad (RAGEvaluatorService) en segundo plano.
        """
        import uuid
        interaction_id = str(uuid.uuid4())
        response.interaction_id = interaction_id
        if log_entry is not None:
            log_entry.interaction_id = interaction_id

        if not self._use_ephemeral_db:
            try:
                from database.connection import get_connection
                import json
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO rag_interactions (id, query, model_used, module, sources_used)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    interaction_id,
                    query[:500],
                    self._last_model_used or "unknown",
                    module,
                    json.dumps(response.sources_used, ensure_ascii=False)
                ))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ Error al persistir rag_interactions: {e}")

            if response.content:
                try:
                    from services.async_feedback_dispatcher import AsyncFeedbackDispatcher
                    AsyncFeedbackDispatcher.dispatch_rag_evaluation(
                        query=query,
                        response_text=response.content,
                        retrieved_chunks=retrieved_chunks,
                        interaction_id=interaction_id,
                        module=module
                    )
                except Exception as e:
                    print(f"⚠️ Error al despachar evaluación asíncrona: {e}")

        return interaction_id


    def _build_prompt(self, user, chapter: str, context_docs: list, lens: str = "Ninguno") -> str:
        """Delegates to the centralised PromptBuilder service."""
        return self.prompt_builder.build_system_prompt(
            user=user,
            chapter=chapter,
            context_docs=context_docs,
            lens=lens,
            mode="study_guide",
        )

    def generate_study_guide(self, user_id: int, chapter: str, lens: str = "Ninguno", bible_text: str = None) -> RAGResponse:
        """
        Main RAG pipeline with observability, coverage check, and structured output:
        1. Checks cache (lazy loading).
        2. Retrieves vectors from ChromaDB with distances.
        3. Coverage check pre-LLM.
        4. Assembles prompt via PromptBuilder.
        5. Calls LLM.
        6. Parses structured JSON response defensively.
        7. Logs everything.
        8. Saves to disk and caches.
        """
        start_time = time.time()
        log_entry = RAGLogEntry(module="study_guide", query=f"{chapter} | lens={lens}")
        
        guide_key = f"user_{user_id}_{chapter.replace(' ', '_').lower()}_{lens.replace(' ', '_').lower()}"
        
        # 1. Check Cache
        if self.cache_repo.is_guide_fresh(guide_key):
            file_path = f"data/generated_courses/{guide_key}.md"
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return RAGResponse(content=f.read())
                    
        # 2. Retrieve Vectors with distances
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        search_query = chapter
        if lens != "Ninguno":
            search_query += f" {lens}"
            
        context_docs, is_covered, distances = self._retrieve_with_reranking(
            search_query, log_entry=log_entry, top_candidates=50, final_top=15
        )
        
        # Inyectar sub-grafo de conocimiento si existe
        subgraph = self.graph_service.retrieve_subgraph(search_query)
        if subgraph:
            context_docs.insert(0, subgraph)
            
        # Inyectar texto bíblico directo si proviene del frontend
        if bible_text:
            context_docs.insert(0, f"[TEXTO BÍBLICO COMPLETO DE {chapter}]\n{bible_text}")
            is_covered = True  # Forzamos cobertura porque tenemos la fuente primaria
        
        # 3. Coverage check pre-LLM → fallback educativo (nunca bloquea)
        # La regla de contexto insuficiente (sección 8 del contexto aplicativo) dicta
        # que el LLM debe responder con transparencia, marcando fallback_no_rag=True,
        # no negarse completamente. El prompt ya tiene esa instrucción embebida.
        if not is_covered:
            log_entry.fallback_no_rag = True
        
        # 4. Assemble Prompt via PromptBuilder
        prompt = self._build_prompt(user, chapter, context_docs, lens)
        
        # 5. Call LLM
        raw_response = self._call_llm(prompt, module="study_guide")
        log_entry.model_used = self._last_model_used
        
        # 6. Parse structured JSON defensively
        response = RAGResponse.parse(raw_response, query_topic=chapter)
        
        # 6.1 Process missing topics for backlog
        self._process_missing_topics(response)
        
        # 7. Log
        log_entry.fallback_no_rag = response.fallback_no_rag
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        # 8. Save and Cache
        os.makedirs("data/generated_courses", exist_ok=True)
        file_path = f"data/generated_courses/{guide_key}.md"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response.content)
            
        self.cache_repo.register_guide(guide_key, file_path)
        
        self._record_interaction_and_dispatch_evaluation(
            query=chapter,
            response=response,
            module="study_guide",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def generate_topic_study(self, user_id: int, topic: str) -> RAGResponse:
        """Generates a comprehensive study on a given topic using vector search and structured output."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="topic_study", query=topic)
        
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        context_docs, is_covered, distances = self._retrieve_with_reranking(
            topic, log_entry=log_entry, top_candidates=50, final_top=15
        )
            
        # Inyectar sub-grafo de conocimiento si existe
        subgraph = self.graph_service.retrieve_subgraph(topic)
        if subgraph:
            context_docs.insert(0, subgraph)
            
        if not is_covered:
            log_entry.fallback_no_rag = True
            
        # We reuse prompt_builder but state mode="topic_study"
        prompt = self.prompt_builder.build_system_prompt(
            user=user,
            chapter=topic,
            context_docs=context_docs,
            lens="Ninguno",
            mode="topic_study"
        )
        
        raw_response = self._call_llm(prompt, module="topic_study")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=topic)
        self._process_missing_topics(response)
        
        log_entry.fallback_no_rag = response.fallback_no_rag
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=topic,
            response=response,
            module="topic_study",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def generate_roadmap(self, user_id: int, topic: str) -> RAGResponse:
        """Generates a progressive study plan (JSON) for a given topic."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="roadmap_generator", query=topic)
        
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content='{"error": "Usuario no encontrado"}')
            
        context_docs, is_covered, distances = self._retrieve_and_check_coverage(
            topic, n_results=5, log_entry=log_entry
        )
        
        context_text = "\n\n".join(context_docs)
        
        prompt = f"""Actúa como un diseñador de currículo teológico pastoral. 
Basado en estos textos de contexto:
{context_text}

Crea un plan de estudio secuencial y progresivo (Roadmap a largo plazo) sobre el tema "{topic}".
Debes diseñar al menos 2 semanas con 3 días cada una como mínimo.

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<Escribe AQUÍ adentro EL JSON DEL ROADMAP escapado como un bloque de código markdown ```json ... ```>",
  "sources_used": ["<manuales RAG>"],
  "fallback_no_rag": {str(log_entry.fallback_no_rag).lower()},
  "recommended_resources": []
}}

El bloque de código markdown dentro de "content" DEBE tener exactamente esta estructura JSON:
{{
  "topic": "{topic}",
  "weeks": [
    {{
      "week_number": 1,
      "theme": "Nombre del tema de la semana",
      "days": [
        {{ "day_number": 1, "title": "Título del día", "task": "Instrucción de estudio", "scripture": "Cita" }}
      ]
    }}
  ]
}}
"""
        raw_response = self._call_llm(prompt, module="roadmap_generator")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=topic)
        
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=topic,
            response=response,
            module="roadmap_generator",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def generate_family_devotional(self, user_id: int, chapter: str, exegesis_text: str = "") -> RAGResponse:
        """Generates a 10-minute family devotional from a chapter or theological exegesis."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="family_devotional", query=chapter)
        
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        contexto_vital = f"El usuario tiene este contexto de vida familiar: '{user.vital_context}'." if user.vital_context else ""
        
        # This module doesn't do a vector search since it uses the exegesis_text provided by the caller
        # So we skip coverage check. We construct a prompt manually but enforcing RAGResponse.
        
        prompt = f"""Actúa como un padre de familia y pastor reformado preparando la adoración familiar en su mesa.
Tienes el siguiente material base (capítulo o exégesis compleja):
"{chapter}"
{exegesis_text}

{contexto_vital}

Tu objetivo es traducir esta teología profunda a un formato de devocional de 10 minutos para la mesa familiar.
Debe ser entendible para un niño pequeño o para un familiar no teólogo, usando analogías cotidianas, pero manteniendo la rigurosidad doctrinal.

ESTRUCTURA OBLIGATORIA:
1. **Verdad Central** (1 oración sencilla).
2. **Explicación Breve** (1-2 párrafos con una analogía simple).
3. **Preguntas para la Mesa** (2 preguntas: una para niños/principiantes, otra para debate más profundo).
4. **Motivo de Oración** (Basado en el texto).

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<el devocional completo en formato markdown>",
  "sources_used": ["Exégesis proveída"],
  "fallback_no_rag": false,
  "recommended_resources": []
}}
"""
        raw_response = self._call_llm(prompt, module="family_devotional", contains_private_data=True)
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=chapter)
        
        log_entry.fallback_no_rag = response.fallback_no_rag
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=chapter,
            response=response,
            module="family_devotional",
            retrieved_chunks=[exegesis_text] if exegesis_text else [],
            log_entry=log_entry
        )
        return response

    def generate_life_alert(self, user_id: int, struggle_text: str) -> RAGResponse:
        """Generates a pastoral response/alert based on a real-life struggle."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="life_alert", query=struggle_text)
        
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        context_docs, is_covered, distances = self._retrieve_with_reranking(
            struggle_text, log_entry=log_entry, top_candidates=50, final_top=10
        )
            
        if not is_covered:
            log_entry.fallback_no_rag = True
            
        context_text = "\n\n".join(context_docs)
        
        prompt = f"""Actúa como un pastor reformado confrontando amorosamente a un miembro de su iglesia.
El miembro acaba de escribir esta lucha o confesión en su diario: "{struggle_text}"

Basado en estos manuales de teología y santidad de la iglesia:
{context_text}

Tu objetivo es darle un "Mini-estudio focalizado" (Alerta de Aplicación) para esta misma noche.
1. No lo condenes, pero tampoco minimices el pecado si lo hay.
2. Cruza su situación real con un principio bíblico encontrado en el contexto.
3. Sugiere una "Aplicación Práctica" concreta.
4. Sé breve (máximo 150 palabras).

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<tu alerta pastoral aquí en markdown>",
  "sources_used": ["<referencias del contexto RAG usado>"],
  "fallback_no_rag": false,
  "recommended_resources": []
}}
"""
        raw_response = self._call_llm(prompt, module="life_alert", contains_private_data=True)
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=struggle_text)
        
        log_entry.fallback_no_rag = response.fallback_no_rag
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=struggle_text,
            response=response,
            module="life_alert",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def generate_hermeneutic_challenge(self, user_id: int, chapter: str) -> RAGResponse:
        """Generates an interactive hermeneutic quiz for the user based on the chapter."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="hermeneutic_challenge", query=chapter)
        
        # Query for hermeneutic rules, poetry, epistles, inductive method
        search_query = f"{chapter} método inductivo hermenéutica"
        context_docs, is_covered, distances = self._retrieve_and_check_coverage(
            search_query, n_results=3, log_entry=log_entry
        )
        
        context_text = "\n\n".join(context_docs)

        prompt = f"""Actúa como un Profesor de Hermenéutica y Exégesis Bíblica de un seminario reformado.
Tu objetivo es ayudar al usuario a practicar la observación e interpretación del texto bíblico. NO le des la respuesta servida.

Basado en el texto bíblico de {chapter} y en estos principios metodológicos:
{context_text}

Diseña un "Desafío Hermenéutico" de 1 sola pregunta abierta para que el usuario responda.
Si es una epístola, desafíalo a encontrar el conector lógico clave, el contraste principal o la estructura.
Si es poesía/Salmo, desafíalo a identificar un paralelismo o una figura de dicción.

FORMATO OBLIGATORIO:
1. **El Desafío:** Formula la pregunta de manera clara, pidiendo que el usuario justifique su respuesta usando el texto.
2. No reveles la respuesta en este paso. Sé animador pero exige rigor.

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<el desafío completo en formato markdown>",
  "sources_used": ["<manuales RAG>"],
  "fallback_no_rag": {str(log_entry.fallback_no_rag).lower()},
  "recommended_resources": []
}}
"""
        raw_response = self._call_llm(prompt, module="hermeneutic_challenge")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=chapter)
        
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=chapter,
            response=response,
            module="hermeneutic_challenge",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response
        
    def evaluate_hermeneutic_answer(self, user_id: int, chapter: str, challenge: str, user_answer: str) -> RAGResponse:
        """Evaluates the user's answer to the hermeneutic challenge."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="hermeneutic_evaluation", query=f"{chapter} | Answer: {user_answer}")
        
        search_query = f"{chapter} método inductivo hermenéutica"
        context_docs, is_covered, distances = self._retrieve_and_check_coverage(
            search_query, n_results=3, log_entry=log_entry
        )
        
        context_text = "\n\n".join(context_docs)

        prompt = f"""Actúa como un Profesor de Hermenéutica y Exégesis Bíblica de un seminario reformado.
Tu objetivo es corregir el ejercicio del alumno. Eres estricto con el método pero muy pastoral y animador.

Capítulo bajo análisis: {chapter}
Pregunta que le hiciste (El Desafío): "{challenge}"
Respuesta del alumno: "{user_answer}"

Basado en el texto bíblico y en estos principios metodológicos:
{context_text}

Evalúa la respuesta:
1. Dale un veredicto claro (ej. "¡Excelente!", "Casi, pero te faltó ver...", "No exactamente").
2. Explica brevemente la respuesta correcta aplicando la regla hermenéutica correspondiente.
3. Cierra con una frase de ánimo para seguir estudiando la Palabra de Dios.

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<la evaluación completa en formato markdown>",
  "sources_used": ["<manuales RAG>"],
  "fallback_no_rag": {str(log_entry.fallback_no_rag).lower()},
  "recommended_resources": []
}}
"""
        raw_response = self._call_llm(prompt, module="hermeneutic_evaluation")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=chapter)
        
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=f"{chapter} | Answer: {user_answer}",
            response=response,
            module="hermeneutic_evaluation",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def chat_evangelism_roleplay(self, user_id: int, scenario: str, chat_history: list) -> str:
        """Acts as the non-believer based on the scenario and responds to the user's latest message."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="chat_evangelism", query=scenario)
        
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        prompt = f"""Actúa como un no creyente en un juego de rol de evangelismo apologético.
Toma el rol que el usuario describió en el siguiente escenario: "{scenario}".

Tu objetivo es responder de manera realista al cristiano con el que estás hablando.
REGLAS:
1. Mantente ESTRICTAMENTE en tu personaje. A veces sé curioso, a veces un poco escéptico o incluso a la defensiva si el personaje lo amerita (ej. si el usuario usó un escenario ateo/nihilista).
2. NO te conviertas fácilmente en el primer ni segundo mensaje.
3. Tus respuestas deben ser coloquiales, naturales, de la vida diaria (no hables como un teólogo del siglo XVI, a menos que el escenario lo pida).
4. No rompas la cuarta pared.
5. Sé breve en tus respuestas, como en un chat normal.

HISTORIAL DE LA CONVERSACIÓN HASTA AHORA:
{history_str}

Responde al último mensaje como el personaje.
"""
        response = self._call_llm(prompt, module="chat_evangelism")
        log_entry.model_used = self._last_model_used
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        return response
        
    def evaluate_evangelism_session(self, user_id: int, scenario: str, chat_history: list) -> RAGResponse:
        """Evaluates the evangelism session using the vector db and returns a structured JSON."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="evaluate_evangelism", query=scenario)
        
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        search_query = "evangelismo apologética alcanzar"
        context_docs, is_covered, distances = self._retrieve_and_check_coverage(
            search_query, n_results=4, log_entry=log_entry
        )
        
        context_text = "\n\n".join(context_docs)

        prompt = f"""Actúa como un pastor reformado experto en apologética y evangelización evaluando a un discípulo.
El usuario acaba de terminar un roleplay (simulación) de evangelismo.

Escenario original: "{scenario}"

HISTORIAL DEL CHAT (El 'user' es el discípulo, 'assistant' fue el incrédulo):
{history_str}

Basado en estos manuales de evangelización y sana doctrina de la iglesia:
{context_text}

Evalúa al discípulo:
1. ¿Fue fiel al evangelio (ley, pecado, gracia, arrepentimiento, fe)?
2. ¿Fue amable y respetuoso (1 Pedro 3:15) o cayó en discusiones inútiles?
3. Cita al menos un principio del contexto recuperado que aplicó bien o que debió haber aplicado.
4. Dale una conclusión alentadora.

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<la evaluación completa en formato markdown>",
  "sources_used": ["<manuales RAG usados>"],
  "fallback_no_rag": {str(log_entry.fallback_no_rag).lower()},
  "recommended_resources": []
}}
"""
        raw_response = self._call_llm(prompt, module="evaluate_evangelism")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic="Evaluación Evangelismo")
        
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        return response

    def generate_gym_exercise(self, user_id: int, exercise_type: str, chapter: str = None) -> RAGResponse:
        start_time = time.time()
        log_entry = RAGLogEntry(module="gym_exercise", query=f"{exercise_type} - {chapter}")
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        search_query = chapter if chapter else exercise_type
        context_docs, is_covered, distances = self._retrieve_and_check_coverage(
            search_query, n_results=3, log_entry=log_entry
        )
        
        prompt = self.prompt_builder.build_system_prompt(
            user=user,
            chapter=chapter if chapter else "Aleatorio",
            context_docs=context_docs,
            lens=exercise_type,
            mode="gym_exercise"
        )
        
        raw_response = self._call_llm(prompt, module="gym_exercise")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic=chapter)
        
        log_entry.fallback_no_rag = response.fallback_no_rag
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=f"{chapter} {exercise_type}",
            response=response,
            module="gym_exercise",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def evaluate_gym_answer(self, user_id: int, exercise_type: str, exercise_context: str, user_answer: str) -> RAGResponse:
        start_time = time.time()
        log_entry = RAGLogEntry(module="gym_evaluation", query=f"{exercise_type} evaluation")
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return RAGResponse(content="Error: Usuario no encontrado.")
            
        # Instead of RAG retrieval, we pass the exercise_context back as the "context_docs"
        context_docs = [exercise_context]
        
        prompt = self.prompt_builder.build_system_prompt(
            user=user,
            chapter=user_answer,
            context_docs=context_docs,
            lens=exercise_type,
            mode="gym_evaluation"
        )
        
        raw_response = self._call_llm(prompt, module="gym_evaluation")
        log_entry.model_used = self._last_model_used
        response = RAGResponse.parse(raw_response, query_topic="Evaluación")
        
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        self._record_interaction_and_dispatch_evaluation(
            query=f"{exercise_type} evaluation: {user_answer}",
            response=response,
            module="gym_evaluation",
            retrieved_chunks=context_docs,
            log_entry=log_entry
        )
        return response

    def generate_exegetical_panel(self, verse: str, raw_resources: str) -> str:
        """Generates an intelligent exegetical connections panel based on raw resources."""
        start_time = time.time()
        log_entry = RAGLogEntry(module="exegetical_panel", query=verse)
        
        prompt = f"""Eres el Motor de Curación de Contenido de una plataforma de exégesis bíblica. 
Tu objetivo es tomar un versículo base y una lista cruda de recursos recuperados del sistema (con sus categorías), y transformarlos en un panel estructurado, explicando BREVEMENTE por qué cada recurso es relevante para el pasaje de estudio.

VERSÍCULO BASE: {verse}
LISTA CRUDA DE RECURSOS: 
{raw_resources}

REGLAS DE FORMATO Y CLASIFICACIÓN OBLIGATORIAS:
1. Divide la respuesta en secciones claras según la categoría del recurso.
2. SECCIÓN 1: "📖 Referencias Cruzadas (Scriptura Scripturam Interpretatur)": Agrupa aquí todos los recursos marcados como (Categoría: cross_reference). No solo los listes; explica en 1 o 2 líneas CÓMO se conectan teológicamente con el versículo base.
3. SECCIÓN 2: "🛠️ Lentes de Estudio y Metodología": Agrupa los manuales (Categoría: general) como diccionarios, guías inductivas o revistas de teología bíblica. Sugiere brevemente cómo aplicar ese método al versículo base.
4. SECCIÓN 3: "💡 Aplicación Pastoral y Consejería": Si hay libros de aplicación (ej. The Pastor and Counseling), indica cómo el principio del versículo base se conecta con la vida práctica o el cuidado del alma.
5. Usa viñetas, negritas para los nombres de los archivos/versículos, y mantén un tono pastoral y académico. 
6. TIENES PROHIBIDO inventar archivos o referencias que no estén en la lista cruda. Si una sección queda vacía, omítela.
"""
        raw_response = self._call_llm(prompt, module="exegetical_panel")
        log_entry.model_used = self._last_model_used
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        return raw_response

    def draft_missing_resource(self, user_id: int, tema: str, motivo: str, tipo: str) -> str:
        """Genera automáticamente una guía para un tema del backlog usando el LLM (Tier 1)."""
        import os
        import re
        import time
        from database.connection import get_connection
        from services.etl_processor import sincronizar_nuevos_archivos
        
        start_time = time.time()
        log_entry = RAGLogEntry(module="draft_backlog", query=tema)
        
        prompt = f"""Eres un Agente Arquitecto y Teólogo Sistemático de la iglesia.
Se ha detectado un vacío en la biblioteca (Backlog) y tu tarea es redactar una guía exegética o un artículo robusto sobre este tema para llenar la brecha temporalmente.

TEMA A DESARROLLAR: {tema}
TIPO DE RECURSO SOLICITADO: {tipo}
MOTIVO DE LA CARENCIA (por qué hizo falta): {motivo}

INSTRUCCIONES OBLIGATORIAS:
1. Escribe un documento en formato Markdown extenso y profundo.
2. Usa teología evangélica/ortodoxa (alineado con la Confesión de Fe de 1689).
3. No uses formato JSON, solo devuelve el texto puro en Markdown.
4. Incluye títulos, subtítulos y citas bíblicas explícitas para sostener tus afirmaciones.
"""
        # Call LLM using a module mapped to Tier 1
        raw_response = self._call_llm(prompt, module="study_guide")
        log_entry.model_used = self._last_model_used
        log_entry.duration_ms = int((time.time() - start_time) * 1000)
        self._populate_log_routing(log_entry)
        self.logger.log(log_entry)
        
        # Guardar en disco (AISLADO para evitar retroalimentación en RAG)
        os.makedirs("estudios_generados", exist_ok=True)
        filename = f"backlog_{tema.replace(' ', '_').lower()}.md"
        # Limpiar filename de caracteres invalidos
        filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '.', '_')]).rstrip()
        file_path = os.path.join("estudios_generados", filename)
        
        # Extraer markdown si viene en block de codigo
        if "```markdown" in raw_response:
            match = re.search(r"```markdown(.*?)```", raw_response, re.DOTALL)
            if match:
                raw_response = match.group(1).strip()
        elif "```" in raw_response:
             match = re.search(r"```(.*?)```", raw_response, re.DOTALL)
             if match:
                raw_response = match.group(1).strip()
        
        content = f"---\ncategory: \"generado_por_ia\"\nresource_type: \"{tipo}\"\n---\n\n{raw_response}"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Marcar en BD como completado
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE temas_pendientes SET estado = 'Completado' WHERE tema_o_libro = ?", (tema,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error DB backlog: {e}")
            
        # Disparar ETL para indexar el nuevo recurso inmediatamente
        sincronizar_nuevos_archivos()
        
        return file_path
