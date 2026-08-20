import streamlit as st
from services.rag_service import RAGService
from repositories.user_repository import UserRepository


def render(user_id: int):
    st.title("💬 Chat Exegético")
    st.caption("Consultá tu biblioteca teológica de forma conversacional. La IA responde exclusivamente con lo que encuentre en tus recursos indexados.")

    user_repo = UserRepository()
    user = user_repo.get_user_by_id(user_id)

    if not user:
        st.error("No se pudo cargar el perfil del usuario.")
        return

    # Initialize chat history in session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Architect Mode Toggle
    st.write("")
    is_architect_mode = st.toggle(
        "🛠️ Modo Arquitecto de Estudio", 
        value=False,
        help="Permite a la IA cruzar tu biblioteca con su conocimiento experto en sintaxis/gramática para diseñarte métodos de estudio a medida (ideal para Análisis Proposicional)."
    )
    st.divider()

    # Chat input
    if prompt := st.chat_input("Hacé una pregunta teológica, pedí un estudio inductivo, o un análisis proposicional..."):
        # Show user message
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Consultando la biblioteca y generando respuesta..."):
                response = _query_rag(user, prompt, st.session_state.chat_messages[:-1], is_architect_mode)
            st.markdown(response)

        st.session_state.chat_messages.append({"role": "assistant", "content": response})


def _query_rag(user, question: str, chat_history: list, is_architect_mode: bool = False) -> str:
    """
    Queries the vector database for relevant context, builds the chat-specific
    system prompt, and sends it to the LLM cascade (Gemini → Groq).
    """
    rag_svc = RAGService()

    # 1. Retrieve relevant context from ChromaDB
    query_embedding = rag_svc.encoder.encode([question]).tolist()

    try:
        results = rag_svc.collection.query(
            query_embeddings=query_embedding,
            n_results=8
        )
    except Exception as e:
        return f"Error al consultar la base de datos vectorial: {e}"

    if not results['documents'] or not results['documents'][0]:
        return "No cuento con recursos suficientes en la biblioteca para responder esto con precisión. Te sugiero consultarlo directamente con el liderazgo de la congregación."

    context_docs = results['documents'][0]
    context_metadatas = results['metadatas'][0] if results['metadatas'] else []

    # 2. Build enriched context with source metadata
    context_parts = []
    for i, (doc, meta) in enumerate(zip(context_docs, context_metadatas)):
        source_info = ""
        tema = meta.get("tema_principal", "")
        seccion = meta.get("seccion", "")
        subtema = meta.get("subtema", "")
        if tema:
            source_info += f" | Tema: {tema}"
        if seccion:
            source_info += f" > {seccion}"
        if subtema:
            source_info += f" > {subtema}"
        context_parts.append(f"[Fragmento {i+1}{source_info}]\n{doc}")

    context_text = "\n\n---\n\n".join(context_parts)

    # 3. Build the chat-specific system prompt
    modo_salida = "discipulado_familiar" if user.family_mode else "estudio_personal"
    nivel = user.study_level if user.study_level else "moderado"

    # Load dynamic hermeneutic rules
    reglas_inyeccion = ""
    try:
        import os, json
        if os.path.exists("data/reglas_hermeneuticas.json"):
            with open("data/reglas_hermeneuticas.json", "r", encoding="utf-8") as f:
                reglas = json.load(f)
                if reglas:
                    reglas_str = "\n".join([f"- {r}" for r in reglas])
                    reglas_inyeccion = f"\nREGLAS HERMENÉUTICAS Y METODOLÓGICAS APRENDIDAS DE LA BIBLIOTECA:\n{reglas_str}\n"
    except Exception:
        pass

    contexto_vital_inyeccion = ""
    if user.vital_context:
        contexto_vital_inyeccion = f"\nCONTEXTO VITAL DEL USUARIO:\nEl usuario ha compartido su situación actual: '{user.vital_context}'. Cuando ofrezcas aplicaciones prácticas (ej. Nivel 5), usa este contexto para dar pasos de acción concretos y relevantes a su realidad.\n"

    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-6:]]) if chat_history else "Sin historial previo."
    
    if is_architect_mode:
        system_prompt = f"""Eres un Arquitecto de Metodologías de Estudio Bíblico y Exégesis. El usuario tiene una biblioteca masiva de recursos teológicos (método inductivo, poesía hebrea, exégesis de epístolas, etc.) pero necesita que le diseñes un método claro y aplicable para su sesión de estudio.

Tu objetivo es CRUZAR la información que recuperes de la base de datos con tu conocimiento experto en análisis bíblico para crear herramientas, pasos a seguir o "Roadmaps" de estudio.
{contexto_vital_inyeccion}
ORQUESTACIÓN DE NIVELES DE ESTUDIO (DEBES guiar al usuario por estos niveles si pide un método estructurado):
- Nivel 1: Vuelo de Pájaro (Lectura Panorámica). Objetivo: Captar la idea general sin frenarse. Leer de corrido, identificar tema y tono del autor.
- Nivel 2: Lupa Inductiva (Observación y Marcado). Objetivo: Ver detalles. Responder las 6 preguntas (Quién, Qué, Cuándo, Dónde, Por qué, Cómo) y marcar verdades absolutas y palabras clave.
- Nivel 3: Bisturí Exegético (Análisis Proposicional y Gramatical). Objetivo: Desarmar la estructura. Separar cláusulas principales/subordinadas, identificar verbos imperativos, preposiciones clave y conectores lógicos.
- Nivel 4: Lente Histórico y Teológico (Contexto Profundo). Objetivo: Entender el detrás de escena. Referencias cruzadas, contexto cultural, y significado en idioma original (griego/hebreo).
- Nivel 5: Espejo y Transformación (Aplicación y Adoración Familiar). Objetivo: Llevar a la práctica. Convertir lo estudiado en plan de acción para paternidad/maternidad/liderazgo con preguntas de introspección.

REGLAS DE OPERACIÓN:
1. SÍNTESIS Y CREATIVIDAD METODOLÓGICA: Si el usuario pide un método para el cual no hay un libro exacto (por ejemplo, "Análisis Proposicional de Epístolas"), utiliza tu conocimiento base sobre sintaxis, gramática y exégesis, y combínalo con los principios de observación/interpretación de los documentos recuperados. 
2. ESTRUCTURA ACCIONABLE: No devuelvas un muro de texto teórico. Devuelve una "Receta" paso a paso basándote en los niveles mencionados (Ej: Nivel 3: Paso 1 Identificar verbos...).
3. EXPANSIÓN DE RECURSOS: Si notas que un principio de "Poesía Hebrea" se puede aplicar al texto que el usuario quiere estudiar, sugiérelo proactivamente. "Sé lo que tengo para ofrecer y te sugiero usar esta herramienta".
4. NOMBRES DE PRUEBA: Al generar cualquier ejemplo práctico o de código para ilustrar el método, tienes ESTRICTAMENTE PROHIBIDO usar nombres reales. Utiliza siempre "Usuario_Prueba", "Pastor_Demo", etc.

CONTEXTO RECUPERADO DE LA BIBLIOTECA DEL USUARIO:
{context_text}

HISTORIAL RECIENTE DEL CHAT:
{history_str}

PETICIÓN DEL USUARIO:
{question}
"""
    else:
        system_prompt = f"""Eres un Asistente Exegético y Teológico de nivel seminario, diseñado para guiar al usuario en el estudio profundo de las Escrituras.

Tu función principal es responder a las consultas del usuario utilizando EXCLUSIVAMENTE los fragmentos de texto recuperados de la base de datos vectorial (contexto RAG).

JERARQUÍA DOCTRINAL (en este orden de autoridad):
1. Texto bíblico (inerrante, autoridad suprema).
2. `apreciacion_de_iglesia.md` — lente hermenéutico principal. Ante cualquier tensión interpretativa, este archivo decide.
3. Confesiones y credos históricos recuperados (incl. Confesión de 1689) — marco de soporte secundario, nunca contradice al punto 2.
{reglas_inyeccion}
{contexto_vital_inyeccion}
RESTRICCIÓN DE CONOCIMIENTO (Groundedness):
- Basa tus respuestas ÚNICAMENTE en el contexto proporcionado.
- Si el contexto recuperado no contiene información suficiente, DEBES responder: "No cuento con recursos suficientes en la biblioteca para responder esto con precisión. Te sugiero consultarlo directamente con el liderazgo de la congregación."
- Cita siempre la fuente cuando expliques un concepto (ej. "Según la guía de estudio inductivo...", "Como indica el fragmento sobre Soteriología...").

REGLA DE VERIFICACIÓN DE FUENTE (obligatoria):
Antes de citar un versículo, un credo o `apreciacion_de_iglesia.md`, confirmá que ese fragmento específico está presente en el contexto entregado en este turno. Nunca cites de memoria.

REGLA DE INFERENCIA VS. DOCTRINA EXPLÍCITA:
Si tu respuesta incluye una conclusión inferida, marcala con "Esto se puede inferir de..." Nunca presentes una inferencia como doctrina explícita.

MÉTODOS DE ESTUDIO:
- ESTUDIO INDUCTIVO (NBEI): Si el usuario pide estudiar un pasaje de forma inductiva, seguí estrictamente el orden Observación → Interpretación → Aplicación, según el nivel configurado.
- ANÁLISIS PROPOSICIONAL: Si el usuario pide análisis proposicional de una epístola, enfocate en la estructura gramatical: cláusula principal, cláusulas subordinadas (con indentación), conectores lógicos en negrita (Porque, Por tanto, Pero, Y, Si). No hagas resumen devocional — desglosá la lógica argumentativa.

NIVEL DE ESTUDIO: {nivel}
MODO DE SALIDA: {modo_salida}

PRIVACIDAD: NUNCA uses nombres reales en ejemplos. Usá siempre "Usuario_Prueba", "Hermano_Demo", "Esposa_Prueba".

FORMATO Y ESTILO:
- Español rioplatense/neutro correcto.
- Usá formato Markdown (negritas para palabras clave, listas para pasos, citas para texto bíblico).
- Revisá ortografía y evitá anglicismos antes de responder.

CERO CREATIVIDAD DOCTRINAL: nunca ofrezcas posturas liberales, nueva revelación, ni "balances" entre posturas teológicas en conflicto cuando `apreciacion_de_iglesia.md` ya tomó una posición.

---
CONTEXTO RECUPERADO DE LA BIBLIOTECA:
{context_text}

HISTORIAL RECIENTE DEL CHAT:
{history_str}

PETICIÓN DEL USUARIO:
{question}
"""

    # 4. Send to LLM cascade
    return rag_svc._call_llm(system_prompt)
