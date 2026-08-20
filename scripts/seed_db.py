import os
import sys
from datetime import date, timedelta

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from models.habit import Habit
from models.journal import JournalEntry
from models.feedback import Feedback
from repositories.user_repository import UserRepository
from repositories.habit_repository import HabitRepository
from repositories.journal_repository import JournalRepository
from repositories.feedback_repository import FeedbackRepository

def run_seed():
    print("Iniciando inyección de datos mock...")
    
    # Asegurar que las tablas existan
    init_db()

    user_repo = UserRepository()
    habit_repo = HabitRepository()
    journal_repo = JournalRepository()
    feedback_repo = FeedbackRepository()

    # 1. Crear Usuarios de Prueba (Multi-Tenant)
    print("-> Creando usuarios...")
    user1 = user_repo.get_user_by_username("Usuario_Prueba_1")
    if not user1:
        user1 = user_repo.create_user("Usuario_Prueba_1", display_name="Juan Perez")
        user_repo.update_study_level(user1.id, "complejo")
    
    user2 = user_repo.get_user_by_username("Usuario_Prueba_2")
    if not user2:
        user2 = user_repo.create_user("Usuario_Prueba_2", display_name="Maria Gomez")
        user_repo.update_study_level(user2.id, "principiante")
        user_repo.toggle_family_mode(user2.id, True)

    print(f"   Usuarios listos: {user1.username} (ID {user1.id}), {user2.username} (ID {user2.id})")

    # 2. Generar Historial en Tracker de Gracia
    print("-> Generando hábitos...")
    today = date.today()
    for i in range(5):
        past_date = today - timedelta(days=i)
        
        # User 1: Very consistent
        habit1 = Habit(
            id=None, user_id=user1.id, date=past_date,
            bible_reading=True, prayer=True, meditation=(i%2==0), family_worship=False,
            notes=f"Nota del día {past_date}" if i == 0 else None
        )
        habit_repo.save_habit(habit1)

        # User 2: Occasional, focuses on family mode
        habit2 = Habit(
            id=None, user_id=user2.id, date=past_date,
            bible_reading=(i%3!=0), prayer=True, meditation=False, family_worship=(i%2==0)
        )
        habit_repo.save_habit(habit2)

    # 3. Insertar Diario Espiritual
    print("-> Generando diarios espirituales...")
    entry1 = JournalEntry(
        id=None, user_id=user1.id, date=today,
        humiliation="Hoy luché con la impaciencia en el trabajo.",
        christ="Recordé que Cristo es paciente para con nosotros, soportando nuestras debilidades.",
        practical_application="Mañana pausaré y oraré 5 segundos antes de responder a un correo tenso."
    )
    journal_repo.save_entry(entry1)

    # 4. Simular Feedback Beta
    print("-> Generando sugerencias beta...")
    feedback1 = Feedback(
        id=None, user_id=user1.id, type="sugerencia",
        message="Me gustaría que el muro de oración tenga notificaciones.",
        page="Muro de Oración"
    )
    feedback_repo.create(feedback1)

    feedback2 = Feedback(
        id=None, user_id=user2.id, type="bug",
        message="El calendario no se actualizó inmediatamente al guardar el hábito.",
        page="Tracker de Gracia"
    )
    feedback_repo.create(feedback2)

    print("Seed completado con exito. Base de datos lista para pruebas manuales.")

if __name__ == '__main__':
    run_seed()
