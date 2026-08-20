import streamlit as st
from datetime import date
from repositories.habit_repository import HabitRepository
from models.habit import Habit

habit_repo = HabitRepository()

def render(user_id: int):
    st.header("Tracker de Gracia")
    
    today = date.today()
    selected_date = st.date_input("Selecciona una fecha", today)
    
    habit = habit_repo.get_habit(user_id, selected_date)
    if not habit:
        habit = Habit(id=None, user_id=user_id, date=selected_date)
    
    st.write(f"Registro para: {selected_date.strftime('%Y-%m-%d')}")
    
    bible = st.checkbox("Lectura Bíblica", value=habit.bible_reading)
    prayer = st.checkbox("Oración", value=habit.prayer)
    
    if st.button("Guardar"):
        habit.bible_reading = bible
        habit.prayer = prayer
        habit_repo.save_habit(habit)
        st.success("Guardado correctamente!")
