import streamlit as st
import json
from services.rag_service import RAGService
from repositories.roadmap_repository import RoadmapRepository
from models.rag_response import RAGResponse
from utils.rag_ui import render_rag_response

def render(user_id: int):
    st.title("Buscador Temático y Exégesis")
    st.markdown("Genera estudios bíblicos temáticos basados en los recursos de tu biblioteca.")
    
    topic = st.text_input("Ingresa un tema a estudiar (ej. 'Adoración Familiar', 'La Gracia')", placeholder="¿Qué tema deseas investigar?")
    
    # Session state for tracking current study
    if 'current_topic' not in st.session_state:
        st.session_state['current_topic'] = None
    if 'current_study' not in st.session_state:
        st.session_state['current_study'] = None
        
    if st.button("Buscar y Generar Estudio"):
        if not topic:
            st.warning("Por favor ingresa un tema válido.")
            return
            
        with st.spinner(f"Consultando recursos teológicos y comentarios sobre '{topic}'..."):
            rag_svc = RAGService()
            study_content = rag_svc.generate_topic_study(user_id, topic)
            
        st.session_state['current_topic'] = topic
        st.session_state['current_study'] = study_content
        
    if st.session_state['current_study']:
        st.success("Estudio generado exitosamente.")
        
        with st.container(border=True):
            render_rag_response(st.session_state['current_study'])
            
        # PDF Export Logic
        from utils.pdf_helper import generar_pdf_desde_markdown
        pdf_bytes = generar_pdf_desde_markdown(st.session_state['current_study'].content)
        if pdf_bytes:
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.download_button(
                    label="🖨️ Descargar en PDF",
                    data=pdf_bytes,
                    file_name=f"estudio_tematico_{st.session_state['current_topic'].replace(' ', '_').lower()}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
                
        st.divider()
        st.subheader("Plan de Estudio (Roadmap)")
        st.markdown(f"Transforma este estudio en una ruta de aprendizaje estructurada paso a paso.")
        
        if st.button("Generar Roadmap a largo plazo"):
            with st.spinner("Diseñando plan progresivo..."):
                rag_svc = RAGService()
                roadmap_response = rag_svc.generate_roadmap(user_id, st.session_state['current_topic'])
                try:
                    # Clean the markdown code blocks from the content
                    json_str = roadmap_response.content.replace("```json", "").replace("```", "").strip()
                    roadmap_data = json.loads(json_str)
                    
                    # Guardar en base de datos
                    repo = RoadmapRepository()
                    repo.create(user_id, st.session_state['current_topic'], roadmap_data)
                    
                    st.success("¡Roadmap generado y guardado! Ve al Dashboard para seguir tu progreso.")
                    with st.expander("Ver estructura del Roadmap", expanded=True):
                        st.json(roadmap_data)
                except Exception as e:
                    st.error(f"Error al generar o interpretar el Roadmap: {e}\nRespuesta recibida: {roadmap_response.content}")
