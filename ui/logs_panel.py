import streamlit as st
import json
import os

def render(user_id: int):
    st.title("📊 Telemetría y Logs RAG")
    
    log_file = "rag_telemetry.jsonl"
    
    if not os.path.exists(log_file):
        st.info("No hay logs de telemetría disponibles aún.")
        return
        
    st.markdown("Revisa las decisiones tomadas por el sistema RAG (Retrieval-Augmented Generation).")
    
    # Read the file
    logs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
                    
    if not logs:
        st.info("El archivo de logs está vacío o corrupto.")
        return
        
    # Order descending
    logs.reverse()
    
    # Render table or cards
    for idx, log in enumerate(logs):
        timestamp = log.get("timestamp", "Desconocido")
        module = log.get("module", "General")
        query = log.get("query", "")
        fallback = log.get("fallback_no_rag", False)
        duration = log.get("duration_ms", 0)
        
        # Color coding
        if fallback:
            status_color = "red"
            status_icon = "⚠️"
            status_text = "Fallback (Sin Contexto Suficiente)"
        else:
            status_color = "green"
            status_icon = "✅"
            status_text = "RAG Exitoso"
            
        with st.expander(f"{status_icon} [{timestamp}] {module} | Query: '{query[:30]}...'", expanded=(idx==0)):
            st.markdown(f"**Módulo**: {module}")
            st.markdown(f"**Query**: {query}")
            st.markdown(f"**Estado**: :{status_color}[{status_text}]")
            st.markdown(f"**Modelo Utilizado**: {log.get('model_used', 'Desconocido')}")
            st.markdown(f"**Duración**: {duration} ms")
            
            chunks = log.get("chunks_retrieved", [])
            st.markdown(f"**Fragmentos Recuperados ({len(chunks)})**:")
            if chunks:
                for c in chunks:
                    st.caption(f"- ID: `{c.get('chunk_id')}` | Score: `{c.get('score', 0):.4f}`")
                    st.caption(f"  *Snippet*: {c.get('snippet', '')}")
            else:
                st.caption("Ninguno.")
