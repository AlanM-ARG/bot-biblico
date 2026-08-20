import streamlit as st
import json
from datetime import datetime, timedelta
from repositories.roadmap_repository import RoadmapRepository
from services.rag_service import RAGService
from streamlit_calendar import calendar

roadmap_repo = RoadmapRepository()

def render(user_id: int):
    st.header("🗺️ Roadmaps de Estudio")
    st.markdown("Genera un plan de estudio a largo plazo. La IA diseñará semanas y días progresivos basados en tu tema.")
    
    # Init RAG
    if 'rag_service' not in st.session_state:
        st.session_state.rag_service = RAGService()

    # Formulario para generar uno nuevo
    with st.expander("Generar Nuevo Roadmap", expanded=False):
        topic = st.text_input("Tema de estudio (ej. Atributos de Dios, Paternidad Bíblica)")
        if st.button("Generar Plan", type="primary"):
            if topic:
                with st.spinner(f"Diseñando currículo para '{topic}'... esto puede demorar."):
                    response = st.session_state.rag_service.generate_roadmap(user_id, topic)
                    if response.fallback_no_rag:
                        st.warning("Se generó un plan, pero faltan recursos en la biblioteca para que sea 100% fiel.")
                    
                    try:
                        # Extraer JSON de la respuesta (usualmente viene entre ```json ... ```)
                        content = response.content
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        
                        roadmap_data = json.loads(content)
                        roadmap_repo.create(user_id, topic, roadmap_data)
                        st.success("¡Roadmap generado y guardado!")
                    except Exception as e:
                        st.error(f"Error parseando el plan generado: {e}")
                        st.code(response.content)

    st.divider()

    # Ver los existentes
    roadmaps = roadmap_repo.get_by_user(user_id)
    
    if not roadmaps:
        st.info("Aún no tienes ningún Roadmap. Genera uno arriba.")
        return
        
    st.subheader("Tus Planes de Estudio")
    
    # Seleccionar el roadmap activo a visualizar
    roadmap_opts = {r['id']: f"{r['topic']} ({r['created_at'][:10]})" for r in roadmaps}
    selected_id = st.selectbox("Selecciona un plan:", options=list(roadmap_opts.keys()), format_func=lambda x: roadmap_opts[x])
    
    selected_roadmap = next((r for r in roadmaps if r['id'] == selected_id), None)
    
    if selected_roadmap:
        roadmap_data = selected_roadmap['roadmap_data']
        created_at_str = selected_roadmap['created_at']
        
        try:
            # Parse datetime safely depending on SQLite format
            created_at = datetime.fromisoformat(created_at_str) if 'T' in created_at_str else datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        except:
            created_at = datetime.now()

        # Transformar a eventos de calendario
        calendar_events = []
        day_counter = 0
        
        # Necesitamos mantener el estado de los completados (podríamos guardarlo en el propio JSON o en reading_progress)
        # Por simplicidad lo leemos del JSON si existe una key "completed_days", o lo creamos
        if "completed_days" not in roadmap_data:
            roadmap_data["completed_days"] = []
            
        completed_days = roadmap_data["completed_days"]
        
        st.write("### Vista de Calendario")
        for week in roadmap_data.get('weeks', []):
            for day in week.get('days', []):
                # Calcular la fecha asumiendo que el Día 1 es la fecha de creación + 1, Día 2 es creación + 2...
                event_date = created_at + timedelta(days=day_counter)
                day_id = f"w{week['week_number']}_d{day['day_number']}"
                
                is_completed = day_id in completed_days
                color = "#28a745" if is_completed else "#007bff"
                
                calendar_events.append({
                    "title": day.get('title', f"Día {day['day_number']}"),
                    "start": event_date.strftime("%Y-%m-%d"),
                    "end": event_date.strftime("%Y-%m-%d"),
                    "color": color,
                    "extendedProps": {
                        "task": day.get("task", ""),
                        "scripture": day.get("scripture", "")
                    }
                })
                day_counter += 1

        calendar_options = {
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,listMonth",
            },
            "initialView": "dayGridMonth",
            "initialDate": created_at.strftime("%Y-%m-%d")
        }

        # Renderizar calendario
        custom_css="""
            .fc-event-past {
                opacity: 0.8;
            }
            .fc-event-time {
                display: none;
            }
            .fc-event-title {
                font-weight: 700;
                color: white;
            }
            .fc-toolbar-title {
                font-size: 1.5rem;
            }
        """

        cal = calendar(events=calendar_events, options=calendar_options, custom_css=custom_css)
        
        st.divider()
        st.write("### Detalles y Progreso")
        
        # Mapeo lineal para checklists
        changes_made = False
        for week in roadmap_data.get('weeks', []):
            with st.expander(f"Semana {week.get('week_number', '?')}: {week.get('theme', 'Sin tema')}"):
                for day in week.get('days', []):
                    day_id = f"w{week['week_number']}_d{day['day_number']}"
                    is_completed = day_id in completed_days
                    
                    st.markdown(f"**Día {day['day_number']}**: {day.get('title', '')}")
                    st.markdown(f"*📝 Tarea*: {day.get('task', '')}")
                    st.markdown(f"*📖 Lectura*: {day.get('scripture', '')}")
                    
                    checked = st.checkbox("Completado", value=is_completed, key=f"check_{selected_id}_{day_id}")
                    if checked and not is_completed:
                        roadmap_data["completed_days"].append(day_id)
                        changes_made = True
                    elif not checked and is_completed:
                        roadmap_data["completed_days"].remove(day_id)
                        changes_made = True
                    st.markdown("---")
                    
        if changes_made:
            # Guardamos el progreso de vuelta en el json
            roadmap_repo.update_roadmap_data(selected_id, roadmap_data)
            # Rerun es necesario para que el calendario tome los nuevos colores
            st.rerun()

        if st.button("🗑️ Eliminar Roadmap", type="secondary"):
            roadmap_repo.delete(selected_id)
            st.success("Eliminado.")
            st.rerun()
