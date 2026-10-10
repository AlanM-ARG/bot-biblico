import streamlit as st
import os
import sqlite3
import shutil
from pathlib import Path
import chromadb
from database.connection import DB_PATH

def render(user_id: int):
    st.title("🛠️ Panel de Administración")
    st.markdown("Centralización de tareas de mantenimiento, ETL y auditorías.")
    
    tab_files, tab_db, tab_etl = st.tabs([
        "📁 Archivos y Huérfanos", 
        "🗄️ Base de Datos", 
        "⚡ ETL y Automatizaciones"
    ])
    
    with tab_files:
        st.subheader("Analizador de Discrepancias (PDF vs MD)")
        st.markdown("Busca PDFs que pesan mucho pero que no generaron suficiente texto (.md). Útil tras OCR defectuosos.")
        if st.button("Analizar y Mover a Reciclaje", key="btn_discrepancias"):
            with st.spinner("Analizando PDFs y extracciones..."):
                _analizar_discrepancias()
                
        st.divider()
        
        st.subheader("Limpieza de Archivos Huérfanos")
        st.markdown("Limpia de SQLite aquellos recursos que ya no existen en `data_raw` (e.g., porque fueron borrados manualmente o divididos).")
        if st.button("Ejecutar Limpieza", key="btn_huerfanos"):
            with st.spinner("Escaneando e identificando huérfanos..."):
                _limpiar_huerfanos()

    with tab_db:
        st.subheader("Checkeo de Salud de la Base de Datos")
        if st.button("Verificar Tablas", key="btn_check_db"):
            with st.spinner("Consultando esquema SQLite..."):
                _check_db()
                
    with tab_etl:
        st.subheader("Sincronización y Procesamiento")
        
        if st.button("⚡ Sincronizar Nuevos Archivos", type="primary", help="Procesa y añade únicamente los archivos que no han sido indexados."):
            from services.etl_processor import sincronizar_nuevos_archivos
            with st.spinner("Convirtiendo PDFs e indexando vectores..."):
                sincronizar_nuevos_archivos()
            st.success("Recursos nuevos sincronizados correctamente.")

        if st.button("⚠️ Reconstruir Biblioteca en Segundo Plano (Blue-Green)", help="Reconstruye toda la base de datos sin interrumpir el uso actual de la aplicación. Al finalizar, hará un swap de los archivos de manera transparente."):
            import subprocess
            with st.spinner("Lanzando tarea en background..."):
                subprocess.Popen(["python", "-m", "scripts.blue_green_rebuild"], cwd=os.getcwd())
            st.success("🚀 Tarea iniciada en segundo plano. Puedes seguir usando la aplicación. Las bases de datos se intercambiarán automáticamente al finalizar.")

        st.divider()
        st.subheader("🧠 Grafo de Conocimiento Teológico (GraphRAG)")
        st.markdown("Extrae entidades teológicas y relaciones semánticas usando el modelo local gratuito de Ollama (`llama3.1`), sin consumir cuota de API.")
        
        from services.graph_service import GraphService
        graph_svc = GraphService()
        stats = graph_svc.get_graph_stats()
        
        col_g1, col_g2, col_g3 = st.columns(3)
        col_g1.metric("Nodos (Entidades)", stats.get("nodes", 0))
        col_g2.metric("Aristas (Relaciones)", stats.get("edges", 0))
        col_g3.metric("Libros en el Grafo", stats.get("resources_indexed", 0))
        
        col_b1, col_b2 = st.columns([2, 1])
        with col_b1:
            batch_size = st.slider("Libros a procesar en este lote", min_value=1, max_value=10, value=3)
        with col_b2:
            st.write("")
            st.write("")
            btn_graph = st.button("🚀 Extraer Lote con Ollama", help="Lee los primeros fragmentos de libros pendientes y extrae relaciones con Ollama local.")
            
        if btn_graph:
            with st.spinner(f"Extrayendo grafo para {batch_size} libros con Ollama local (esto puede tomar 1-2 minutos)..."):
                res = graph_svc.build_graph_batch(max_resources=batch_size, chunks_per_resource=4)
                if res.get("processed", 0) > 0:
                    st.success(res.get("message", "Lote procesado exitosamente."))
                    st.rerun()
                else:
                    st.info(res.get("message", "No hay recursos pendientes."))
        st.subheader("Auditoría y Automatización")

        if st.button("🛡️ Auditoría Doctrinal a Lotes", help="Cruza recursos pendientes contra la Confesión de 1689."):
            with st.spinner("Ejecutando auditoría con IA... esto puede demorar varios minutos."):
                from scripts.auditor_doctrinal import AuditorDoctrinal
                auditor = AuditorDoctrinal()
                archivos = auditor.run_audit_batch()
                st.success(f"¡Auditoría completada! {len(archivos)} recursos evaluados.")

        if st.button("⚖️ Ejecutar Análisis Doctrinal (Feedback)", help="Procesa manualmente el feedback con errores doctrinales para penalizar documentos."):
            from services.feedback_analyzer import FeedbackAnalyzer
            with st.spinner("Revisando feedback_beta..."):
                analyzer = FeedbackAnalyzer()
                res = analyzer.process_doctrinal_penalties()
                st.success(f"Análisis completado: {res.get('feedbacks_revisados', 0)} feedbacks revisados. {len(res.get('documentos_penalizados', {}))} penalizados.")
        
        if st.button("🔍 Ejecutar Evaluación RAG (Auto-Backlog)", help="Evalúa manualmente interacciones pendientes y genera tickets en temas_pendientes."):
            with st.spinner("Ejecutando evaluador RAG..."):
                # Ejecutamos la lógica que antes estaba en scheduler_service
                import json
                from database.connection import get_connection
                from services.rag_evaluator import RAGEvaluatorService

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.id, r.query, r.module, r.sources_used
                    FROM rag_interactions r
                    LEFT JOIN rag_evaluations e ON r.id = e.interaction_id
                    WHERE e.id IS NULL
                    ORDER BY r.timestamp DESC
                    LIMIT 10
                """)
                rows = cursor.fetchall()
                conn.close()

                if rows:
                    evaluator = RAGEvaluatorService()
                    for row in rows:
                        inter_id = row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
                        query = row["query"] if isinstance(row, dict) or hasattr(row, "keys") else row[1]
                        module = row["module"] if isinstance(row, dict) or hasattr(row, "keys") else row[2]
                        sources_raw = row["sources_used"] if isinstance(row, dict) or hasattr(row, "keys") else row[3]
                        try:
                            sources = json.loads(sources_raw) if sources_raw else []
                        except Exception:
                            sources = []

                        evaluator.evaluate_interaction(
                            query=query,
                            response_text="",
                            retrieved_chunks=sources,
                            interaction_id=inter_id,
                            module=module or "general"
                        )
                    st.success(f"Evaluación completada para {len(rows)} interacciones pendientes.")
                else:
                    st.info("No hay interacciones pendientes de evaluar.")

        if st.button("🔔 Enviar Recordatorio (Discord)"):
            from cron_reminders import trigger_discord_reminder
            with st.spinner("Generando y enviando recordatorio..."):
                success = trigger_discord_reminder()
            if success:
                st.success("✅ ¡Recordatorio enviado al canal!")
            else:
                st.error("❌ Faltó configurar DISCORD_WEBHOOK_URL en .env o hubo un error de red.")

# --- Funciones Auxiliares (Extraídas de los scripts CLI) ---

def _analizar_discrepancias():
    procesados_dir = Path("pdfs_procesados")
    data_raw_dir = Path("data_raw")
    discrepancias = []

    if not procesados_dir.exists() or not data_raw_dir.exists():
        st.error("Los directorios de PDFS procesados o data_raw no existen.")
        return

    for pdf_file in procesados_dir.glob("*.pdf"):
        md_file = data_raw_dir / (pdf_file.stem + ".md")
        
        if md_file.exists():
            pdf_size_mb = pdf_file.stat().st_size / (1024 * 1024)
            try:
                md_text = md_file.read_text(encoding="utf-8").strip()
                md_size_kb = len(md_text.encode("utf-8")) / 1024
            except Exception:
                md_size_kb = 0
            
            # Criterio original: PDF > 2MB pero MD < 10KB
            if pdf_size_mb > 2.0 and md_size_kb < 10.0:
                discrepancias.append(pdf_file)

    if not discrepancias:
        st.info("No se encontraron archivos con discrepancias sospechosas.")
    else:
        st.warning(f"Se encontraron {len(discrepancias)} archivos. Moviendo a pdfs_nuevos/ y eliminando sus .md...")
        Path("pdfs_nuevos").mkdir(exist_ok=True)
        reciclados = []
        for pdf_file in discrepancias:
            md_file = data_raw_dir / (pdf_file.stem + ".md")
            destino_pdf = Path("pdfs_nuevos") / pdf_file.name
            safe_name = pdf_file.name.encode('ascii', 'ignore').decode('ascii')
            reciclados.append(safe_name)
            
            try:
                if md_file.exists():
                    md_file.unlink()
            except Exception:
                pass
                
            try:
                shutil.move(str(pdf_file), str(destino_pdf))
            except Exception:
                pass
                
        st.write("Archivos reciclados:")
        st.code("\n".join(reciclados))
        st.success("Limpieza completada exitosamente.")

def _limpiar_huerfanos():
    raw_dir = Path('data_raw')
    archivos_fisicos = set()
    if raw_dir.exists():
        for md_file in raw_dir.glob('**/*.md'):
            archivos_fisicos.add(md_file.name)
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    except Exception as e:
        st.error(f"Error conectando a BD: {e}")
        return
        
    cursor.execute("SELECT id, filepath FROM resources")
    recursos_db = cursor.fetchall()
    
    archivos_en_db = {os.path.basename(path) for id, path in recursos_db if path}
    huerfanos = archivos_en_db - archivos_fisicos
    
    if not huerfanos:
        st.info("No hay archivos huérfanos. SQLite y disco están sincronizados.")
        conn.close()
        return
        
    st.warning(f"Se encontraron {len(huerfanos)} archivos huérfanos.")
    st.code("\n".join(list(huerfanos)))
    
    for h in huerfanos:
        cursor.execute("DELETE FROM resources WHERE filepath LIKE ?", (f"%{h}",))
    conn.commit()
    conn.close()
    
    st.success("Huérfanos eliminados de SQLite. (Nota: Si siguen apareciendo en ChromaDB, considera Reconstruir Biblioteca).")

def _check_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for t in tables:
            table_name = t[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            cols = cursor.fetchall()
            
            with st.expander(f"Tabla: {table_name}"):
                col_data = [{"ID": c[0], "Name": c[1], "Type": c[2]} for c in cols]
                st.dataframe(col_data, use_container_width=True)
                
        conn.close()
    except Exception as e:
        st.error(f"Error chequeando base de datos: {e}")
