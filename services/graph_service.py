import json
import sqlite3
import litellm
from database.connection import get_connection

class GraphService:
    def __init__(self):
        self.model = "ollama/llama3.1"
        self.api_base = "http://localhost:11434"
    
    def get_connection(self):
        return get_connection()

    def extract_entities_and_relations(self, text: str, resource_id: int, chunk_id: str):
        """
        Obliga a usar Ollama local para extraer el grafo de conocimiento del texto
        sin consumir cuota de la API.
        """
        prompt = f"""Actúa como un teólogo reformado extrayendo conocimiento.
Lee el siguiente texto y extrae "Entidades" (conceptos teológicos, personas, libros) y "Relaciones" entre ellas.
Las relaciones deben ser verbos o acciones cortas (ej. "justifica", "escribió", "enseña sobre", "se opone a").

Texto:
{text}

Responde ÚNICAMENTE con un JSON válido usando este esquema exacto:
{{
    "entities": [
        {{"name": "NombreEntidad", "type": "Concepto/Persona/Libro/Doctrina", "description": "Breve descripción"}}
    ],
    "relationships": [
        {{"source": "NombreEntidad1", "target": "NombreEntidad2", "relationship": "verbo/acción"}}
    ]
}}
"""
        try:
            response = litellm.completion(
                model=self.model,
                api_base=self.api_base,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
                timeout=120
            )
            raw_text = response.choices[0].message.content
            
            # Limpiar posible markdown code block
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            
            self._save_to_db(data, resource_id, chunk_id)
            return True
            
        except Exception as e:
            print(f"⚠️ Error en extracción de grafo (Ollama): {e}")
            return False
            
    def _save_to_db(self, data: dict, resource_id: int, chunk_id: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])
        
        for e in entities:
            # Upsert entity
            cursor.execute("""
                INSERT INTO graph_nodes (id, entity_name, entity_type, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(entity_name) DO UPDATE SET 
                    description=excluded.description 
                WHERE description IS NULL
            """, (e["name"].lower().replace(" ", "_"), e["name"].upper(), e["type"], e.get("description", "")))
            
        for r in relationships:
            cursor.execute("""
                INSERT INTO graph_edges (source_entity, target_entity, relationship, resource_id, chunk_id)
                VALUES (?, ?, ?, ?, ?)
            """, (r["source"].upper(), r["target"].upper(), r["relationship"], resource_id, chunk_id))
            
        conn.commit()
        conn.close()

    def retrieve_subgraph(self, query: str) -> str:
        """
        Extrae un resumen del grafo para pasárselo al LLM en el prompt.
        1. Identifica posibles entidades en la query.
        2. Busca relaciones de esas entidades.
        """
        # Simplificación para el MVP: Buscamos palabras de la query en graph_nodes
        query_words = [w.upper() for w in query.split() if len(w) > 4]
        if not query_words:
            return ""
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholders = " OR ".join(["entity_name LIKE ?" for _ in query_words])
        params = [f"%{w}%" for w in query_words]
        
        cursor.execute(f"SELECT entity_name FROM graph_nodes WHERE {placeholders}", params)
        matched_entities = [row[0] for row in cursor.fetchall()]
        
        if not matched_entities:
            conn.close()
            return ""
            
        # Extraer relaciones de 1 salto (1-hop)
        placeholders2 = ",".join(["?"] * len(matched_entities))
        cursor.execute(f"""
            SELECT source_entity, relationship, target_entity 
            FROM graph_edges 
            WHERE source_entity IN ({placeholders2}) OR target_entity IN ({placeholders2})
            LIMIT 20
        """, matched_entities * 2)
        
        edges = cursor.fetchall()
        conn.close()
        
        if not edges:
            return ""
            
        graph_text = "Relaciones teológicas encontradas en el Grafo de Conocimiento:\n"
        for s, r, t in edges:
            graph_text += f"- {s} --[{r}]--> {t}\n"
            
        return graph_text

    def get_graph_stats(self) -> dict:
        """Devuelve estadísticas de nodos y aristas en el grafo de conocimiento."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM graph_nodes")
            nodes_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM graph_edges")
            edges_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT resource_id) FROM graph_edges WHERE resource_id IS NOT NULL")
            resources_indexed = cursor.fetchone()[0]
            conn.close()
            return {
                "nodes": nodes_count,
                "edges": edges_count,
                "resources_indexed": resources_indexed
            }
        except Exception as e:
            return {"nodes": 0, "edges": 0, "resources_indexed": 0, "error": str(e)}

    def build_graph_batch(self, max_resources: int = 5, chunks_per_resource: int = 4) -> dict:
        """
        Construye el grafo de conocimiento progresivamente por lotes sin bloquear la vectorización principal.
        Procesa hasta max_resources libros que aún no estén en el grafo, extrayendo hasta chunks_per_resource chunks por libro.
        """
        import os
        from services.vector_service import VectorService
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener recursos pendientes de indexar en el grafo
        cursor.execute("""
            SELECT id, filename, filepath 
            FROM resources 
            WHERE id NOT IN (SELECT DISTINCT resource_id FROM graph_edges WHERE resource_id IS NOT NULL)
            LIMIT ?
        """, (max_resources,))
        
        pending_resources = cursor.fetchall()
        conn.close()
        
        if not pending_resources:
            return {"processed": 0, "message": "Todos los recursos disponibles ya fueron incorporados al grafo."}
            
        vector_svc = VectorService()
        processed_count = 0
        total_edges_before = self.get_graph_stats().get("edges", 0)
        
        for r_id, filename, filepath in pending_resources:
            if not os.path.exists(filepath):
                continue
                
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                clean_content = vector_svc._strip_frontmatter(content)
                chunks = vector_svc.chunk_text(clean_content)
                
                # Seleccionar primeros N chunks representativos
                selected_chunks = chunks[:chunks_per_resource]
                for i, c in enumerate(selected_chunks):
                    chunk_id = f"res_{r_id}_chunk_{i}"
                    self.extract_entities_and_relations(c["text"], r_id, chunk_id)
                    
                processed_count += 1
            except Exception as e:
                print(f"⚠️ Error procesando {filename} para GraphRAG: {e}")
                
        total_edges_after = self.get_graph_stats().get("edges", 0)
        return {
            "processed": processed_count,
            "new_edges": total_edges_after - total_edges_before,
            "message": f"Se procesaron {processed_count} libros en el Grafo de Conocimiento (+{total_edges_after - total_edges_before} relaciones)."
        }

