import streamlit as st
from repositories.user_repository import UserRepository

def render():
    st.title("Bienvenido al Peregrino")
    st.markdown("Inicia sesión o regístrate para acceder a tu diario, tracker y estudio personalizado.")
    
    user_repo = UserRepository()
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario (Ej. alan_peregrino)")
        
        col1, col2 = st.columns(2)
        with col1:
            submit_login = st.form_submit_button("Ingresar")
        with col2:
            submit_register = st.form_submit_button("Crear Nuevo Peregrino")
            
        if submit_login:
            if not usuario:
                st.error("Por favor, ingresa un nombre de usuario.")
            else:
                user = user_repo.get_user_by_username(usuario)
                if user:
                    st.session_state['user_id'] = user.id
                    st.session_state['usuario_actual'] = user.username
                    st.success(f"¡Bienvenido de nuevo, {user.display_name}!")
                    st.rerun()
                else:
                    st.error("Usuario no encontrado. Revisa el nombre o crea uno nuevo.")
                    
        if submit_register:
            if not usuario:
                st.error("Por favor, ingresa un nombre de usuario.")
            else:
                existing = user_repo.get_user_by_username(usuario)
                if existing:
                    st.warning("Este usuario ya existe. Usa el botón 'Ingresar'.")
                else:
                    new_user = user_repo.create_user(usuario)
                    st.session_state['user_id'] = new_user.id
                    st.session_state['usuario_actual'] = new_user.username
                    st.success(f"¡Cuenta creada! Bienvenido, {new_user.display_name}.")
                    st.rerun()
