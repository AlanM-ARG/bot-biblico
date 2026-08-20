import streamlit as st
from services.rag_service import RAGService

def render(user_id: int):
    st.header("⚔️ Simulador de Evangelismo (Roleplay Bot)")
    st.markdown("Practica tus respuestas apologéticas y de evangelización con la IA actuando como un no creyente.")
    
    # Initialize session state for this screen
    if "evangelism_scenario" not in st.session_state:
        st.session_state["evangelism_scenario"] = None
    if "evangelism_chat" not in st.session_state:
        st.session_state["evangelism_chat"] = []
    if "evangelism_evaluation" not in st.session_state:
        st.session_state["evangelism_evaluation"] = None
        
    # Scenario Configuration
    if not st.session_state["evangelism_scenario"]:
        st.info("Primero, configura con quién vas a hablar.")
        with st.form("scenario_form"):
            scenario_input = st.text_area(
                "Describe al personaje incrédulo", 
                value="Un compañero de trabajo remoto, agnóstico, que pregunta en Slack por qué los cristianos creen que Jesús es el único camino.",
                help="Puedes hacerlo tan difícil o específico como quieras."
            )
            if st.form_submit_button("Comenzar Simulación", type="primary"):
                st.session_state["evangelism_scenario"] = scenario_input
                # El bot da el primer paso
                st.session_state["evangelism_chat"] = [
                    {"role": "assistant", "content": f"*[Entra en personaje basándose en: {scenario_input}]* ¡Hola! Me quedé pensando en eso que hablamos el otro día..."}
                ]
                st.rerun()
    else:
        # Chat Interface
        col1, col2 = st.columns([3, 1])
        
        with col2:
            st.markdown("### Controles")
            st.info(f"**Escenario:** {st.session_state['evangelism_scenario']}")
            
            if st.button("Finalizar y Evaluar"):
                with st.spinner("El pastor está revisando la conversación..."):
                    rag = RAGService()
                    eval_result = rag.evaluate_evangelism_session(
                        user_id, 
                        st.session_state["evangelism_scenario"], 
                        st.session_state["evangelism_chat"]
                    )
                    st.session_state["evangelism_evaluation"] = eval_result
            
            if st.button("Reiniciar Simulador", type="secondary"):
                st.session_state["evangelism_scenario"] = None
                st.session_state["evangelism_chat"] = []
                st.session_state["evangelism_evaluation"] = None
                st.rerun()
                
        with col1:
            if st.session_state["evangelism_evaluation"]:
                st.success("Simulación finalizada.")
                st.subheader("📋 Evaluación Pastoral")
                from utils.rag_ui import render_rag_response
                render_rag_response(st.session_state["evangelism_evaluation"])
            else:
                # Mostrar chat
                chat_container = st.container(height=500)
                with chat_container:
                    for msg in st.session_state["evangelism_chat"]:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])
                            
                # Input del usuario
                user_input = st.chat_input("Escribe tu respuesta...")
                if user_input:
                    # Añadir mensaje del usuario
                    st.session_state["evangelism_chat"].append({"role": "user", "content": user_input})
                    
                    # Generar respuesta de la IA
                    with st.spinner("El incrédulo está escribiendo..."):
                        rag = RAGService()
                        bot_response = rag.chat_evangelism_roleplay(
                            user_id, 
                            st.session_state["evangelism_scenario"], 
                            st.session_state["evangelism_chat"]
                        )
                        st.session_state["evangelism_chat"].append({"role": "assistant", "content": bot_response})
                        
                    st.rerun()
