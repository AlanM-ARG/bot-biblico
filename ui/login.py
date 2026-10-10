import streamlit as st
from repositories.user_repository import UserRepository

def render():
    st.title("Bienvenido a Teos AI")
    st.markdown("Ingresá tu nombre de usuario para acceder a tu diario, tracker y estudio personalizado.")
    
    user_repo = UserRepository()
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario (Ej. alan_peregrino)")
        submit_login = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            
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
                    new_user = user_repo.create_user(usuario)
                    st.session_state['user_id'] = new_user.id
                    st.session_state['usuario_actual'] = new_user.username
                    st.success(f"¡Cuenta creada! Bienvenido, {new_user.display_name}.")
                    st.rerun()

