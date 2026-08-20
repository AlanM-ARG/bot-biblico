import streamlit as st
import os

def inject_custom_css():
    """Reads the style.css file and injects it into the Streamlit app."""
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"No se encontró el archivo de estilos en {css_path}")
