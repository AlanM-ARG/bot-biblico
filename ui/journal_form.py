import streamlit as st
from datetime import date
from repositories.journal_repository import JournalRepository
from models.journal import JournalEntry
from models.rag_response import RAGResponse

journal_repo = JournalRepository()

def render(user_id: int):
    st.header("Diario Espiritual")
    
    today = date.today()
    selected_date = st.date_input("Selecciona una fecha", today, key="journal_date")
    
    entry = journal_repo.get_entry(user_id, selected_date)
    if not entry:
        entry = JournalEntry(id=None, user_id=user_id, date=selected_date)
    
    with st.form("journal_form"):
        st.subheader("1. Humillación y Confesión")
        humiliation = st.text_area("¿Qué pecados, actitudes o pensamientos necesitas confesar hoy?", value=entry.humiliation)
        
        st.subheader("2. Contemplando a Cristo")
        christ = st.text_area("¿Cómo se revela el evangelio o la obra de Cristo en lo que has leído o meditado?", value=entry.christ)
        
        st.subheader("3. Aplicación Práctica")
        practical_application = st.text_area("¿Qué acción específica, cambio de mente o devoción requiere esto de ti?", value=entry.practical_application)
        
        submitted = st.form_submit_button("Guardar Entrada")
        if submitted:
            entry.humiliation = humiliation
            entry.christ = christ
            entry.practical_application = practical_application
            journal_repo.save_entry(entry)
            st.success("Diario guardado correctamente!")

    if entry.humiliation and len(entry.humiliation) > 10:
        st.divider()
        st.subheader("🛡️ Consultorio Pastoral (IA)")
        st.markdown("Deja que la IA cruce tu confesión actual con los manuales de santidad de la biblioteca.")
        
        if st.button("Generar Alerta de Aplicación"):
            with st.spinner("Buscando consejo bíblico en la biblioteca..."):
                from services.rag_service import RAGService
                rag = RAGService()
                alerta_response = rag.generate_life_alert(user_id, entry.humiliation)
                
                # Opcional: auto-guardar en aplicación práctica si está vacía
                if not entry.practical_application and isinstance(alerta_response, RAGResponse):
                    entry.practical_application = alerta_response.content
                    journal_repo.save_entry(entry)
                    st.info("La respuesta se ha guardado automáticamente en tu Aplicación Práctica.")
                    
                st.session_state["ultima_alerta_vida"] = alerta_response
                
        if st.session_state.get("ultima_alerta_vida"):
            with st.container(border=True):
                result = st.session_state["ultima_alerta_vida"]
                if isinstance(result, RAGResponse):
                    if result.fallback_no_rag:
                        st.warning("⚠️ **Consejo pastoral generado sin manuales locales específicos.**")
                        if result.recommended_resources:
                            st.info("Recursos que ayudarían: " + ", ".join(result.recommended_resources))
                    st.markdown(result.content)
                    if result.sources_used:
                        with st.expander("Fuentes"):
                            st.write(", ".join(result.sources_used))
                else:
                    st.markdown(result)
