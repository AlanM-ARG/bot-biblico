import streamlit as st
from services.rag_service import RAGService

def render(user_id: int):
    st.title("🏋️ Gimnasio Hermenéutico")
    st.markdown("Pon a prueba tus habilidades de interpretación bíblica. Selecciona una categoría y desafíate a ti mismo resolviendo los ejercicios planteados por la IA basándose en las reglas exegéticas del ecosistema.")

    # Initialize RAG Service
    if 'rag_service' not in st.session_state:
        st.session_state.rag_service = RAGService()

    # Session state for gym
    if 'gym_step' not in st.session_state:
        st.session_state.gym_step = 'select' # select -> challenge -> feedback
    if 'gym_exercise' not in st.session_state:
        st.session_state.gym_exercise = None
    if 'gym_context' not in st.session_state:
        st.session_state.gym_context = None

    # Step 1: Selection
    if st.session_state.gym_step == 'select':
        st.subheader("Configura tu Desafío")
        
        exercise_type = st.selectbox(
            "Categoría de Ejercicio",
            ["Epístolas Paulinas", "Poesía Hebrea", "Narrativa Histórica"]
        )
        
        chapter_input = st.text_input("Libro o Capítulo específico (Opcional, ej. 'Romanos 8' o dejalo en blanco)")
        
        if st.button("Generar Desafío", type="primary"):
            with st.spinner("Preparando el ejercicio hermenéutico..."):
                response = st.session_state.rag_service.generate_gym_exercise(
                    user_id=user_id,
                    exercise_type=exercise_type,
                    chapter=chapter_input if chapter_input else "Aleatorio"
                )
                if response.fallback_no_rag:
                    st.warning("No se encontraron suficientes recursos para generar este ejercicio. Intenta con otro pasaje.")
                else:
                    st.session_state.gym_exercise = response.content
                    st.session_state.gym_context = exercise_type  # In a real scenario, we might want to store the exact RAG chunks
                    st.session_state.gym_type = exercise_type
                    st.session_state.gym_step = 'challenge'
                    st.rerun()

    # Step 2: Challenge
    elif st.session_state.gym_step == 'challenge':
        st.subheader("Tu Desafío")
        st.info(st.session_state.gym_exercise)
        
        st.markdown("---")
        user_answer = st.text_area("Tu Análisis:", height=150, placeholder="Escribe tu respuesta aplicando las reglas hermenéuticas...")
        
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Cancelar", key="cancel"):
                st.session_state.gym_step = 'select'
                st.session_state.gym_exercise = None
                st.rerun()
        with col2:
            if st.button("Enviar Respuesta", type="primary", key="submit_answer"):
                if not user_answer.strip():
                    st.warning("Por favor, escribe una respuesta.")
                else:
                    with st.spinner("Evaluando tu respuesta..."):
                        # To keep context simple, we pass the exercise itself as context so the LLM remembers the question
                        feedback = st.session_state.rag_service.evaluate_gym_answer(
                            user_id=user_id,
                            exercise_type=st.session_state.gym_type,
                            exercise_context=st.session_state.gym_exercise,
                            user_answer=user_answer
                        )
                        st.session_state.gym_feedback = feedback.content
                        st.session_state.gym_step = 'feedback'
                        st.rerun()

    # Step 3: Feedback
    elif st.session_state.gym_step == 'feedback':
        st.subheader("Tu Desafío")
        st.info(st.session_state.gym_exercise)
        
        st.subheader("Evaluación y Retroalimentación")
        st.success(st.session_state.gym_feedback)
        
        if st.button("Hacer Otro Ejercicio", type="primary"):
            st.session_state.gym_step = 'select'
            st.session_state.gym_exercise = None
            st.session_state.gym_feedback = None
            st.rerun()
