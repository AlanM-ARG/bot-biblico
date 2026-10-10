import streamlit as st
import os
import sys

if sys.platform == 'win32':
    # El servidor de Streamlit arranca antes de leer app.py, por lo que cambiar la política 
    # de asyncio llega tarde. Para lograr "0 errores", silenciamos la función interna de Windows.
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        def silenced_call_connection_lost(self, exc):
            try:
                if self._sock is not None:
                    import socket
                    self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self._closed = True
        _ProactorBasePipeTransport._call_connection_lost = silenced_call_connection_lost
    except ImportError:
        pass

from dotenv import load_dotenv

# Cargar variables de entorno (como GEMINI_API_KEY)
load_dotenv()

from database.connection import init_db
from repositories.user_repository import UserRepository
from ui import login, dashboard, study_screen, topic_engine, library, chat_screen, evangelism_screen, logs_panel, hermeneutic_gym, roadmaps, admin_panel
from repositories.feedback_repository import FeedbackRepository
from models.feedback import Feedback
from services.scheduler_service import SchedulerService
from core.constants import ADMIN_USERS

# Initialize database
init_db()

@st.cache_resource
def init_background_jobs():
    scheduler = SchedulerService()
    scheduler.start()
    return scheduler

# Start cron jobs
init_background_jobs()

# Page config
st.set_page_config(page_title="Teos AI", page_icon="📖", layout="wide")

# Inject custom UI styling
from utils.ui_helper import inject_custom_css
inject_custom_css()

# Simple user session management for MVP
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

user_repo = UserRepository()

if st.session_state['user_id'] is None:
    login.render()
else:
    st.sidebar.title(f"Hola, {st.session_state.get('usuario_actual', 'Peregrino')}")
    
    is_admin = st.session_state.get('usuario_actual') in ADMIN_USERS
    
    pages = ["Dashboard del Peregrino", "💬 Chat Exegético", "Buscador Temático", "Pantalla de Estudio", "Biblioteca", "⚔️ Simulador Evangelismo", "🏋️ Gimnasio Hermenéutico", "🗺️ Roadmaps de Estudio"]
    if is_admin:
        pages.append("📊 Logs (RAG)")
        pages.append("🛠️ Panel de Administración")
        
    page = st.sidebar.radio("Ir a", pages)
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state['user_id'] = None
        st.session_state['usuario_actual'] = None
        st.session_state['chat_messages'] = []
        st.rerun()

    if page == "Dashboard del Peregrino":
        dashboard.render(st.session_state['user_id'])
    elif page == "💬 Chat Exegético":
        chat_screen.render(st.session_state['user_id'])
    elif page == "Buscador Temático":
        topic_engine.render(st.session_state['user_id'])
    elif page == "Pantalla de Estudio":
        study_screen.render(st.session_state['user_id'])
    elif page == "Biblioteca":
        library.render(st.session_state['user_id'])
    elif page == "⚔️ Simulador Evangelismo":
        evangelism_screen.render(st.session_state['user_id'])
    elif page == "🏋️ Gimnasio Hermenéutico":
        hermeneutic_gym.render(st.session_state['user_id'])
    elif page == "🗺️ Roadmaps de Estudio":
        roadmaps.render(st.session_state['user_id'])
    elif page == "📊 Logs (RAG)":
        logs_panel.render(st.session_state['user_id'])
    elif page == "🛠️ Panel de Administración":
        admin_panel.render(st.session_state['user_id'])

    # --- Configuración de Usuario ---
    st.sidebar.divider()
    st.sidebar.subheader("⚙️ Configuración")
    user = user_repo.get_user_by_id(st.session_state['user_id'])
    if user:
        new_level = st.sidebar.selectbox(
            "Nivel de Estudio",
            options=["principiante", "moderado", "complejo"],
            index=["principiante", "moderado", "complejo"].index(user.study_level),
            help="Define la profundidad exegética del Asistente IA."
        )
        if new_level != user.study_level:
            user_repo.update_study_level(user.id, new_level)
            st.rerun()

        new_family = st.sidebar.toggle(
            "Modo Discipulado Familiar", 
            value=user.family_mode,
            help="Adapta el lenguaje para el culto familiar."
        )
        if new_family != user.family_mode:
            user_repo.toggle_family_mode(user.id, new_family)
            st.rerun()

        # Contexto Vital
        st.sidebar.markdown("---")
        with st.sidebar.form("vital_context_form"):
            new_context = st.text_area(
                "Contexto Vital",
                value=user.vital_context if user.vital_context else "",
                help="Describí tu situación actual (ej: trabajo remoto, desafíos, familia) para que la IA personalice las aplicaciones prácticas.",
                height=150
            )
            if st.form_submit_button("Guardar Contexto"):
                if new_context != user.vital_context:
                    user_repo.update_vital_context(user.id, new_context)
                    st.success("Contexto actualizado.")
                    st.rerun()

    # --- Configuración de Usuario ---


    # --- Feedback Beta Module in Sidebar ---
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Feedback Beta")
    with st.sidebar.expander("Sugerencias / Reportar Error"):
        with st.form("feedback_form"):
            fb_type = st.selectbox("Tipo", ["sugerencia", "bug", "critica"])
            fb_message = st.text_area("Mensaje")
            submit_fb = st.form_submit_button("Enviar")
            
            if submit_fb and fb_message:
                fb_repo = FeedbackRepository()
                fb = Feedback(
                    id=None,
                    user_id=st.session_state['user_id'],
                    type=fb_type,
                    message=fb_message,
                    page=page
                )
                fb_repo.create(fb)
                st.success("¡Gracias por tu aporte!")
