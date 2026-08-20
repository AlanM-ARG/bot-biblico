import os
import re
import streamlit as st
import os
import json
from ui import journal_form
from services.rag_service import RAGService
from services.cross_reference_service import CrossReferenceService
from services.propositional_service import PropositionalService
from repositories.user_repository import UserRepository
from models.rag_response import RAGResponse
from utils.rag_ui import render_rag_response

def render(user_id: int):
    st.title("Pantalla de Estudio")
    
    col_biblia, col_interaccion = st.columns([6, 4])
    
    # --- Dynamic Bible Reader ---
    bibles_dir = "data/processed/bibles"
    available_bibles = {} # { "NBLA": { "Genesis": [1, 2, 3] } }
    
    if os.path.exists(bibles_dir):
        for f in os.listdir(bibles_dir):
            match = re.match(r"^([A-Z0-9]+)_(.+)_(\d+)\.md$", f)
            if match:
                version = match.group(1)
                book_name = match.group(2).replace('_', ' ')
                chap_num = int(match.group(3))
                
                if version not in available_bibles:
                    available_bibles[version] = {}
                if book_name not in available_bibles[version]:
                    available_bibles[version][book_name] = []
                available_bibles[version][book_name].append((chap_num, f))
                
    with col_interaccion:
        st.subheader("Buscador")
        if available_bibles:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                versiones = sorted(list(available_bibles.keys()))
                selected_version = st.selectbox("Versión", versiones)
                
            with c2:
                canonical_books = [
                    "Génesis", "Éxodo", "Levítico", "Números", "Deuteronomio",
                    "Josué", "Jueces", "Rut", "1 Samuel", "2 Samuel", "1 Reyes", "2 Reyes",
                    "1 Crónicas", "2 Crónicas", "Esdras", "Nehemías", "Ester", "Job",
                    "Salmos", "Proverbios", "Eclesiastés", "Cantares", "Isaías", "Jeremías",
                    "Lamentaciones", "Ezequiel", "Daniel", "Oseas", "Joel", "Amós", "Abdías",
                    "Jonás", "Miqueas", "Nahúm", "Habacuc", "Sofonías", "Hageo", "Zacarías",
                    "Malaquías", "Mateo", "Marcos", "Lucas", "Juan", "Hechos", "Romanos",
                    "1 Corintios", "2 Corintios", "Gálatas", "Efesios", "Filipenses", "Colosenses",
                    "1 Tesalonicenses", "2 Tesalonicenses", "1 Timoteo", "2 Timoteo", "Tito",
                    "Filemón", "Hebreos", "Santiago", "1 Pedro", "2 Pedro", "1 Juan", "2 Juan",
                    "3 Juan", "Judas", "Apocalipsis"
                ]
                
                def get_order_index(b_name: str) -> int:
                    b = b_name.replace("S ", "").replace("San ", "")
                    if "Cantar" in b: b = "Cantares"
                    elif "Hechos" in b: b = "Hechos"
                    elif b == "Salmo": b = "Salmos"
                    
                    try:
                        return canonical_books.index(b)
                    except ValueError:
                        return 999

                libros_ordenados = sorted(list(available_bibles[selected_version].keys()), key=get_order_index)
                selected_book = st.selectbox("Libro", libros_ordenados)
                
            with c3:
                capitulos = sorted(available_bibles[selected_version][selected_book], key=lambda x: x[0])
                chap_nums = [c[0] for c in capitulos]
                selected_chap_num = st.selectbox("Capítulo", chap_nums)
            
            selected_file = next(c[1] for c in capitulos if c[0] == selected_chap_num)
        else:
            st.info("No hay biblias indexadas. Ve a la Biblioteca para procesar una.")
            selected_version, selected_book, selected_chap_num, selected_file = None, None, None, None
            
        st.divider()
        tab_exegesis, tab_teologia, tab_contexto, tab_familiar, tab_diario = st.tabs([
            "Exégesis", "Lente Teológico", "Contexto & Referencias", "Discipulado Familiar", "📝 Tu Diario"
        ])
        
    with col_biblia:
        st.subheader("Lectura Bíblica")
        if selected_file:
            file_path = os.path.join(bibles_dir, selected_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Remove yaml frontmatter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                        
            with st.container(border=True, height=700):
                st.markdown(content)
        else:
            st.info("Selecciona un capítulo en el panel derecho.")
        
        with tab_diario:
            st.markdown("### 📝 Tu Diario Espiritual")
            st.markdown("Registra tu confesión, observaciones y aplicaciones prácticas.")
            journal_form.render(user_id)
            
        with tab_exegesis:
            st.markdown("### Guía Exegética (RAG)")
            if selected_book and selected_chap_num:
                capitulo_str = f"{selected_book} {selected_chap_num}"
                
                opciones_lente = ["Ninguno", "Lente Inductivo", "Lente Eclesiológico 9Marcas", "Lente Histórico", "🔬 Lente Sintáctico-Gramatical"]
                lente_seleccionado = st.selectbox("👓 Seleccionar Lente Exegético", opciones_lente, help="Fuerza al modelo a interpretar el texto priorizando un tipo de manual específico de tu biblioteca. El Lente Sintáctico-Gramatical aplica el método de 5 pasos proposicionales adaptado al género literario del libro.")
                
                cache_key_exegesis = f"exegesis_{selected_book}_{selected_chap_num}_{lente_seleccionado}"
                if cache_key_exegesis not in st.session_state:
                    st.session_state[cache_key_exegesis] = None
                
                # Lente Sintáctico-Gramatical: usa PropositionalService en vez de RAG
                if lente_seleccionado == "🔬 Lente Sintáctico-Gramatical":
                    genre_detected = PropositionalService.detect_genre(selected_book)
                    user = UserRepository().get_user_by_id(user_id)
                    user_level = user.study_level if user else "moderado"
                    st.caption(f"📖 Género detectado: **{genre_detected.capitalize()}** | Nivel de andamiaje: **{user_level.capitalize()}**")
                    
                    if st.button("Generar Análisis Sintáctico-Gramatical"):
                        # Leer el texto bíblico actual
                        if selected_file:
                            file_path = os.path.join(bibles_dir, selected_file)
                            with open(file_path, "r", encoding="utf-8") as f:
                                bible_text = f.read()
                                if bible_text.startswith("---"):
                                    parts = bible_text.split("---", 2)
                                    if len(parts) >= 3:
                                        bible_text = parts[2].strip()
                            
                            with st.spinner(f"Analizando {capitulo_str} como {genre_detected} (nivel {user_level})..."):
                                prop_svc = PropositionalService()
                                analysis = prop_svc.analyze_with_lens(bible_text, selected_book, user_level)
                                st.session_state[cache_key_exegesis] = analysis
                            st.success("Análisis Sintáctico-Gramatical completado.")
                        else:
                            st.warning("Selecciona un capítulo en el panel de lectura.")
                else:
                    if st.button("Generar Estudio de este Capítulo"):
                        with st.spinner(f"Consultando la base doctrinal con {lente_seleccionado} para {capitulo_str}..."):
                            rag = RAGService()
                            guia = rag.generate_study_guide(user_id, capitulo_str, lens=lente_seleccionado)
                            st.session_state[cache_key_exegesis] = guia
                        st.success("Estudio cargado exitosamente.")
                    
                if st.session_state[cache_key_exegesis]:
                    st.markdown("---")
                    render_rag_response(st.session_state[cache_key_exegesis])
                    
                    # PDF Export Logic
                    from utils.pdf_helper import generar_pdf_desde_markdown
                    pdf_bytes = generar_pdf_desde_markdown(st.session_state[cache_key_exegesis].content)
                    if pdf_bytes:
                        st.write("") # spacing
                        col_pdf, _ = st.columns([1, 2])
                        with col_pdf:
                            st.download_button(
                                label="🖨️ Descargar en PDF",
                                data=pdf_bytes,
                                file_name=f"guia_estudio_{capitulo_str.replace(' ', '_').lower()}.pdf",
                                mime="application/pdf",
                                type="primary",
                                key="btn_pdf_guia"
                            )
            else:
                st.warning("Selecciona un capítulo primero.")
                
        with tab_teologia:
            st.markdown("### Teología Sistemática")
            st.markdown("Consulta rápida de la Doctrina Bíblica indexada.")
            
            consulta_teologica = st.text_input("Buscar concepto (ej. 'Trinidad', 'Expiación')", placeholder="¿Qué quieres consultar?")
            if st.button("Buscar Doctrina"):
                if consulta_teologica:
                    with st.spinner("Buscando en los apuntes teológicos..."):
                        from services.vector_service import VectorService
                        vec_svc = VectorService()
                        
                        query_embedding = vec_svc.encoder.encode([consulta_teologica]).tolist()
                        results = vec_svc.collection.query(
                            query_embeddings=query_embedding,
                            n_results=3,
                            where={"category": "documento"}
                        )
                        
                        docs = results['documents'][0] if results['documents'] else []
                        if docs:
                            st.success("Resultados encontrados:")
                            for i, doc in enumerate(docs):
                                with st.expander(f"Fragmento {i+1}", expanded=(i==0)):
                                    st.markdown(doc)
                        else:
                            st.info("No se encontraron referencias doctrinales directas para esta búsqueda.")
                else:
                    st.warning("Escribe un concepto a buscar.")

        with tab_contexto:
            st.markdown("### Contexto Histórico y Referencias Cruzadas")
            if selected_book and selected_chap_num:
                st.subheader("🔗 Material Relacionado en tu Biblioteca")
                
                selected_verse = st.text_input("Versículo específico (opcional)", placeholder="Ej. 28")
                search_query = f"{selected_book} {selected_chap_num}"
                if selected_verse:
                    search_query += f":{selected_verse}"
                    
                if st.button("Buscar Referencias"):
                    with st.spinner(f"Buscando conexiones para {search_query}..."):
                        cross_svc = CrossReferenceService()
                        exact_related = cross_svc.get_exact_references(selected_book, selected_chap_num)
                        sem_related = cross_svc.get_related_resources(search_query, limit=3)
                        
                        all_related_dict = {r.id: r for r in exact_related + sem_related}
                        all_related = list(all_related_dict.values())
                        
                    if all_related:
                        raw_list_str = ""
                        for res in all_related:
                            import json
                            try:
                                meta = json.loads(res.metadata_json)
                                title = meta.get("titulo", res.filename)
                            except:
                                title = res.filename
                            raw_list_str += f"- {title} (Categoría: {res.category})\n"
                            
                        rag = RAGService()
                        panel_md = rag.generate_exegetical_panel(search_query, raw_list_str)
                        
                        st.markdown("### 🔗 Panel de Conexiones Exegéticas")
                        st.markdown(panel_md)
                        
                        # PDF Export Logic
                        pdf_bytes = generar_pdf_desde_markdown(panel_md)
                        if pdf_bytes:
                            st.write("")
                            col_pdf, _ = st.columns([1, 2])
                            with col_pdf:
                                st.download_button(
                                    label="🖨️ Descargar Panel en PDF",
                                    data=pdf_bytes,
                                    file_name=f"panel_exegetico_{search_query.replace(' ', '_').replace(':', '_').lower()}.pdf",
                                    mime="application/pdf",
                                    type="primary",
                                    key=f"btn_pdf_panel_{search_query}"
                                )
                    else:
                        st.info(f"No se encontraron materiales para {search_query}.")
            else:
                st.warning("Selecciona un capítulo primero.")

        with tab_familiar:
            st.markdown("### 👨‍👩‍👦 De la Exégesis a la Mesa")
            if selected_book and selected_chap_num:
                st.info("Genera un devocional familiar de 10 minutos adaptado a tu Contexto Vital.")
                capitulo_str = f"{selected_book} {selected_chap_num}"
                
                if st.button("Generar Devocional Familiar", type="primary"):
                    with st.spinner("Traduciendo teología profunda a lenguaje familiar..."):
                        rag = RAGService()
                        cache_key_exegesis = f"exegesis_{selected_book}_{selected_chap_num}_ninguno"
                        exegesis_previa_obj = st.session_state.get(cache_key_exegesis, "")
                        exegesis_previa = exegesis_previa_obj.content if isinstance(exegesis_previa_obj, RAGResponse) else str(exegesis_previa_obj)
                        
                        devocional_response = rag.generate_family_devotional(user_id, capitulo_str, exegesis_text=exegesis_previa)
                        st.session_state[f"devocional_{capitulo_str}"] = devocional_response
                        
                if st.session_state.get(f"devocional_{capitulo_str}"):
                    with st.container(border=True):
                        render_rag_response(st.session_state[f"devocional_{capitulo_str}"])
                        
                    # PDF Export Logic
                    from utils.pdf_helper import generar_pdf_desde_markdown
                    pdf_bytes = generar_pdf_desde_markdown(st.session_state[f"devocional_{capitulo_str}"].content)
                    if pdf_bytes:
                        st.write("")
                        col_pdf, _ = st.columns([1, 2])
                        with col_pdf:
                            st.download_button(
                                label="🖨️ Descargar Devocional en PDF",
                                data=pdf_bytes,
                                file_name=f"devocional_familiar_{capitulo_str.replace(' ', '_').lower()}.pdf",
                                mime="application/pdf",
                                type="primary",
                                key=f"btn_pdf_devocional_{capitulo_str}"
                            )
            else:
                st.warning("Selecciona un capítulo primero.")
