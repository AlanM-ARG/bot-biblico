import streamlit as st
from models.rag_response import RAGResponse

def render_rag_response(result):
    """
    Renders a RAGResponse object in Streamlit, automatically handling the
    markdown content, fallback warnings, recommended resources, sources_used,
    and granular user feedback (FeedbackBeta) for automated doctrinal audit.
    If the result is just a string, renders it directly.
    """
    if isinstance(result, RAGResponse):
        if result.fallback_no_rag:
            st.warning("⚠️ **Contenido generado sin base bibliotecaria verificada.**")
            if result.recommended_resources:
                st.info("Sugerencias de recursos a indexar: " + ", ".join(result.recommended_resources))
        
        from services.theological_dictionary import TheologicalDictionary
        content_with_tooltips = TheologicalDictionary.highlight_terms(result.content)
        st.markdown(content_with_tooltips, unsafe_allow_html=True)
        
        if result.sources_used:
            with st.expander("Fuentes utilizadas"):
                st.write(", ".join(result.sources_used))

        # --- Micro-componente de Feedback Beta y Auditoría Doctrinal ---
        if result.interaction_id:
            inter_id = result.interaction_id
            state_key = f"fb_given_{inter_id}"
            report_mode_key = f"report_mode_{inter_id}"

            if st.session_state.get(state_key):
                st.caption("✅ *Gracias por tu valoración sobre esta respuesta.*")
            else:
                st.write("")
                col_up, col_down, _ = st.columns([1, 1, 6])
                with col_up:
                    if st.button("👍 Útil", key=f"btn_up_{inter_id}"):
                        try:
                            from models.feedback import FeedbackBeta
                            from repositories.feedback_repository import FeedbackRepository
                            fb = FeedbackBeta(
                                interaction_id=inter_id,
                                rating=1,
                                motivo="Útil",
                                comentario_libre=None
                            )
                            FeedbackRepository().create_beta(fb)
                            st.session_state[state_key] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar voto: {e}")

                with col_down:
                    if st.button("👎 Reportar", key=f"btn_down_{inter_id}"):
                        st.session_state[report_mode_key] = not st.session_state.get(report_mode_key, False)

                if st.session_state.get(report_mode_key):
                    with st.container():
                        st.markdown("##### 🛡️ Reportar problema con esta respuesta")
                        motivo = st.selectbox(
                            "Motivo del reporte",
                            options=[
                                "Error Doctrinal (desvío teológico o confesional)",
                                "Alucinación / No sustentado en las fuentes",
                                "Respuesta incompleta o superficial",
                                "Otro"
                            ],
                            key=f"motivo_{inter_id}"
                        )
                        comentario = st.text_area(
                            "Detalles adicionales (opcional)",
                            placeholder="Describí qué afirmación es errónea o qué fuente se contradice...",
                            key=f"coment_{inter_id}"
                        )
                        if st.button("Enviar Reporte", key=f"btn_submit_rep_{inter_id}", type="primary"):
                            try:
                                from models.feedback import FeedbackBeta
                                from repositories.feedback_repository import FeedbackRepository
                                from services.async_feedback_dispatcher import AsyncFeedbackDispatcher

                                is_doctrinal = "Error Doctrinal" in motivo
                                motivo_clean = "Error Doctrinal" if is_doctrinal else motivo

                                fb = FeedbackBeta(
                                    interaction_id=inter_id,
                                    rating=-1,
                                    motivo=motivo_clean,
                                    comentario_libre=comentario or None
                                )
                                FeedbackRepository().create_beta(fb)
                                st.session_state[state_key] = True
                                st.session_state[report_mode_key] = False

                                # Si es Error Doctrinal, disparar análisis asíncrono de inmediato
                                if is_doctrinal:
                                    AsyncFeedbackDispatcher.dispatch_feedback_analysis()

                                st.success("Reporte enviado. Si se confirman fallos doctrinales, las fuentes serán revisadas y degradadas automáticamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al enviar reporte: {e}")
    else:
        from services.theological_dictionary import TheologicalDictionary
        content_with_tooltips = TheologicalDictionary.highlight_terms(str(result))
        st.markdown(content_with_tooltips, unsafe_allow_html=True)
