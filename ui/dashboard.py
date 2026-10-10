import streamlit as st
from datetime import date, timedelta
from repositories.habit_repository import HabitRepository
from repositories.resource_repository import ResourceRepository
from repositories.roadmap_repository import RoadmapRepository
from models.habit import Habit
from utils.ui_helpers import generate_heatmap_data

def render(user_id: int):
    st.title("Dashboard del Peregrino")
    st.markdown("Un resumen de tu disciplina espiritual y motivos de oración activos.")
    
    col1, col2 = st.columns([6, 4])
    habit_repo = HabitRepository()
    resource_repo = ResourceRepository()
    today = date.today()
    
    with col1:
        st.subheader("Tracker de Gracia")
        st.markdown("Progreso de los últimos 30 días.")
        
        # Fetch last 30 days
        habits = []
        for i in range(30):
            d = today - timedelta(days=i)
            h = habit_repo.get_habit(user_id, d)
            if h:
                habits.append(h)
                
        heatmap = generate_heatmap_data(habits, today, 30)
        
        # --- Metrics Calculation ---
        dias_seguidos = 0
        for i in range(30):
            d_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if heatmap.get(d_str, 0) > 0:
                dias_seguidos += 1
            else:
                if i == 0:
                    continue # Si hoy no hay registro, no rompe la racha si ayer sí hubo
                break
                
        lecturas_mes = sum(1 for v in heatmap.values() if v > 0)
        
        cm1, cm2 = st.columns(2)
        cm1.metric("🔥 Días Seguidos (Racha)", f"{dias_seguidos} días")
        cm2.metric("📅 Lecturas este mes", f"{lecturas_mes}")
        st.write("") # spacing
        
        # --- FullCalendar View (same component as Roadmaps) ---
        from streamlit_calendar import calendar as st_calendar
        
        year, month = today.year, today.month
        
        # Fetch all habits for the current month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        calendar_events = []
        for i in range((last_day - first_day).days + 1):
            d = first_day + timedelta(days=i)
            h = habit_repo.get_habit(user_id, d)
            if h:
                items = []
                if h.bible_reading: items.append("📖")
                if h.prayer: items.append("🙏")
                if h.meditation: items.append("🤔")
                if h.family_worship: items.append("👨‍👩‍👧")
                score = len(items)
                
                if score > 0:
                    if score == 1: color = "#9be9a8"
                    elif score == 2: color = "#40c463"
                    elif score == 3: color = "#30a14e"
                    else: color = "#216e39"
                    
                    calendar_events.append({
                        "title": " ".join(items),
                        "start": d.strftime("%Y-%m-%d"),
                        "end": d.strftime("%Y-%m-%d"),
                        "color": color,
                    })

        calendar_options = {
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "",
            },
            "initialView": "dayGridMonth",
            "initialDate": today.strftime("%Y-%m-%d"),
            "locale": "es",
            "height": 420,
        }

        custom_css = """
            .fc-event-time { display: none; }
            .fc-event-title { font-size: 0.85rem; }
            .fc-toolbar-title { font-size: 1.2rem !important; }
            .fc-daygrid-day-number { font-size: 0.85rem; }
            .fc-day-today { background-color: rgba(74, 158, 255, 0.08) !important; }
        """

        st_calendar(events=calendar_events, options=calendar_options, custom_css=custom_css, key="habit_calendar")
        
        st.divider()
        st.subheader("Registro de Hoy")
        
        # Get today's habit
        todays_habit = habit_repo.get_habit(user_id, today)
        if not todays_habit:
            todays_habit = Habit(id=None, user_id=user_id, date=today)
            
        with st.form("habit_input_form"):
            c1, c2 = st.columns(2)
            with c1:
                bible = st.checkbox("📖 Lectura Bíblica", value=todays_habit.bible_reading)
                prayer = st.checkbox("🙏 Oración", value=todays_habit.prayer)
            with c2:
                meditation = st.checkbox("🤔 Meditación / Autoexamen", value=todays_habit.meditation)
                family = st.checkbox("👨‍👩‍👧 Culto Familiar", value=todays_habit.family_worship)
                
            notes = st.text_input("Nota breve (opcional)", value=todays_habit.notes or "")
            
            submitted = st.form_submit_button("Guardar Disciplinas")
            if submitted:
                todays_habit.bible_reading = bible
                todays_habit.prayer = prayer
                todays_habit.meditation = meditation
                todays_habit.family_worship = family
                todays_habit.notes = notes
                habit_repo.save_habit(todays_habit)
                st.success("¡Registro guardado exitosamente!")
                st.rerun()
            
    with col2:
        # --- Roadmaps Generados ---
        roadmap_repo = RoadmapRepository()
        user_roadmaps = roadmap_repo.get_by_user(user_id)
        if user_roadmaps:
            st.subheader("🗺️ Mis Roadmaps de Discipulado")
            for rm in user_roadmaps:
                with st.container(border=True):
                    st.markdown(f"**{rm['topic']}**")
                    with st.expander("Ver Plan de Estudio"):
                        roadmap_data = rm['roadmap_data']
                        weeks = roadmap_data.get('weeks', [])
                        for w_idx, week in enumerate(weeks):
                            st.markdown(f"**Semana {week.get('week_number', w_idx+1)}: {week.get('theme', '')}**")
                            daily_readings = week.get('daily_readings', [])
                            for d_idx, day_info in enumerate(daily_readings):
                                day_num = day_info.get('day', d_idx+1)
                                passage = day_info.get('passage', '')
                                focus = day_info.get('focus', '')
                                completed = day_info.get('completed', False)
                                
                                ck_key = f"rm_{rm['id']}_w{w_idx}_d{d_idx}"
                                new_val = st.checkbox(f"Día {day_num}: {passage} - {focus}", value=completed, key=ck_key)
                                
                                if new_val != completed:
                                    day_info['completed'] = new_val
                                    roadmap_repo.update_roadmap_data(rm['id'], roadmap_data)
                                    
                                    # Integración Visual con Tracker de Gracia
                                    if new_val:
                                        todays_habit_rm = habit_repo.get_habit(user_id, today)
                                        if not todays_habit_rm:
                                            todays_habit_rm = Habit(id=None, user_id=user_id, date=today)
                                        todays_habit_rm.bible_reading = True
                                        habit_repo.save_habit(todays_habit_rm)
                                        st.toast("¡Progreso del Roadmap y Lectura Bíblica guardados!")
                                        st.rerun()
            
        # --- Reactive UI: Reading Plans ---
        reading_plans = resource_repo.get_by_category("plan_lectura")
        if reading_plans:
            st.subheader("📖 Planes de Lectura Activos")
            for plan in reading_plans:
                with st.container(border=True):
                    # For MVP we just show the filename as the plan name, later we extract from metadata
                    import json
                    try:
                        meta = json.loads(plan.metadata_json)
                        title = meta.get("titulo", plan.filename)
                    except:
                        title = plan.filename
                    st.markdown(f"**{title}**")
                    st.button("Ver Plan", key=f"plan_{plan.id}")
            st.divider()

        # --- Reactive UI: Prayer Wall ---
        st.subheader("Muro de Oración")
        prayer_resources = resource_repo.get_by_category("oracion")
        
        if not prayer_resources:
            st.info("No hay motivos de oración ingresados. Agrega recursos con la categoría 'oracion' para verlos aquí.")
        else:
            for item in prayer_resources:
                with st.container(border=True):
                    import json
                    try:
                        meta = json.loads(item.metadata_json)
                        title = meta.get("titulo", "Motivo General")
                    except:
                        title = "Motivo General"
                        
                    st.markdown(f"**{title}**")
                    # In a real app we'd parse the markdown content of the prayer file
                    # For now we just show a preview or note
                    st.caption(f"Ref: {item.filename}")
                    st.button("🙏 Oré por esto", key=f"pray_res_{item.id}")
