import sqlite3
import streamlit as st
import os
import tempfile
from services.resource_service import ResourceService
from services.vector_service import VectorService
from database.connection import DB_PATH

def render(user_id: int):
    st.title("📚 Biblioteca y Auditoría")
    
    col_upload, col_audit = st.columns([7, 3])
    with col_audit:
        if st.button("🛡️ Ejecutar Auditoría Doctrinal a Lotes", use_container_width=True):
            with st.spinner("Ejecutando auditoría con IA... esto puede demorar varios minutos."):
                from scripts.auditor_doctrinal import AuditorDoctrinal
                auditor = AuditorDoctrinal()
                archivos = auditor.run_audit_batch()
                st.success(f"¡Auditoría completada! Se evaluaron {len(archivos)} recursos nuevos.")
                st.rerun()

    tab_upload, tab_audit_ok, tab_audit_wait, tab_backlog = st.tabs([
        "⬆️ Subir Recurso", 
        "✅ Libros Auditados", 
        "⏳ Esperando PDF",
        "💡 Backlog de Temas"
    ])
    
    with tab_upload:
        st.markdown("Sube tus recursos (Markdown o Audio) para inyectarlos en la inteligencia del aplicativo.")
        uploaded_file = st.file_uploader("Sube un archivo (.md, .mp3, .wav)", type=["md", "mp3", "wav", "m4a"])
        
        if st.button("Procesar Archivo"):
            if uploaded_file is not None:
                with st.spinner("Procesando archivo... Si es audio, Whisper está transcribiendo."):
                    suffix = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name
                        
                    try:
                        resource_svc = ResourceService()
                        resource = resource_svc.ingest_file(tmp_path)
                        
                        if not resource:
                            st.error("Error al ingerir el recurso.")
                        else:
                            st.success(f"Recurso guardado en DB (ID: {resource.id})")
                            
                            st.info("Vectorizando recurso en ChromaDB...")
                            vector_svc = VectorService()
                            success = vector_svc.vectorize_resource(resource)
                            
                            if success:
                                st.success("¡Recurso inyectado al Cerebro exitosamente! Caché invalidada.")
                            else:
                                st.warning("El recurso se guardó pero no pudo ser vectorizado.")
                    except Exception as e:
                        st.error(f"Ocurrió un error: {e}")
                    finally:
                        os.unlink(tmp_path)
            else:
                st.warning("Por favor sube un archivo primero.")

    # --- Fetch Data for Audit and Backlog ---
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT titulo, autor, categoria, estado_revision, justificacion FROM auditoria_libros")
        auditoria_filas = cursor.fetchall()
        
        cursor.execute("SELECT tema_o_libro, motivo_necesidad, tipo_recurso_requerido, estado FROM temas_pendientes")
        temas_filas = cursor.fetchall()
    except sqlite3.OperationalError:
        # Tables might not exist if DB not initialized fully
        auditoria_filas = []
        temas_filas = []
        
    conn.close()

    with tab_audit_ok:
        st.subheader("Filtro Estricto - Confesión 1689")
        for titulo, autor, categoria, estado_revision, justificacion in auditoria_filas:
            if categoria != "Pendiente":
                color = "green" if categoria == "Alineado" else ("orange" if categoria == "Precaución" else "red")
                st.markdown(f"**{titulo}** — *{autor}* | Estado: :{color}[**{categoria}**]")
                st.caption(f"**Veredicto IA:** {justificacion}")
                st.divider()
                
    with tab_audit_wait:
        st.info("Estos recursos fueron sugeridos pero el sistema aún no detecta el archivo `.md` para auditarlos.")
                
        for titulo, autor, categoria, estado_revision, justificacion in auditoria_filas:
            if categoria == "Pendiente":
                st.markdown(f"**{titulo}** — *{autor}* | Estado: :blue[**{estado_revision}**]")
                st.caption(f"Nota: {justificacion}")
                st.divider()

    with tab_backlog:
        st.subheader("🤖 Backlog Automático Detectado por la IA")
        st.markdown("Recursos, guías o análisis que la IA notó que faltan al intentar estudiar ciertos pasajes.")
        
        for tema, motivo, tipo, estado in temas_filas:
            with st.expander(f"📌 [{tipo}] {tema} - Estado: {estado}"):
                st.write(f"**Motivo de carencia detectada:** {motivo}")
                if estado != 'Completado':
                    if st.button(f"Generar Guía Automática para {tema}", key=f"gen_{tema}"):
                        with st.spinner("🤖 El Agente Arquitecto está redactando el recurso basándose en su conocimiento teológico. Por favor espera..."):
                            from services.rag_service import RAGService
                            rag = RAGService()
                            file_path = rag.draft_missing_resource(user_id=user_id, tema=tema, motivo=motivo, tipo=tipo)
                            st.success(f"¡Recurso redactado e indexado! Guardado en: {file_path}")
                            st.rerun()

