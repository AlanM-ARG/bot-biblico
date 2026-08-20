import streamlit as st
from models.rag_response import RAGResponse

def render_rag_response(result):
    """
    Renders a RAGResponse object in Streamlit, automatically handling the
    markdown content, fallback warnings, recommended resources, and sources_used.
    If the result is just a string, renders it directly.
    """
    if isinstance(result, RAGResponse):
        if result.fallback_no_rag:
            st.warning("⚠️ **Contenido generado sin base bibliotecaria verificada.**")
            if result.recommended_resources:
                st.info("Sugerencias de recursos a indexar: " + ", ".join(result.recommended_resources))
        
        st.markdown(result.content)
        
        if result.sources_used:
            with st.expander("Fuentes utilizadas"):
                st.write(", ".join(result.sources_used))
    else:
        st.markdown(str(result))
