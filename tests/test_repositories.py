import pytest
from datetime import date
from models.habit import Habit
from models.feedback import Feedback
from repositories.user_repository import UserRepository
from repositories.habit_repository import HabitRepository
from repositories.feedback_repository import FeedbackRepository

def test_user_repository_crud():
    repo = UserRepository()
    
    # 1. Create user
    user = repo.create_user("test_user_1", display_name="Test User")
    assert user.id is not None
    assert user.username == "test_user_1"
    assert user.study_level == "principiante"
    assert user.family_mode is False

    # 2. Update study level
    repo.update_study_level(user.id, "complejo")
    updated_user = repo.get_user_by_id(user.id)
    assert updated_user.study_level == "complejo"

    # 3. Toggle family mode
    repo.toggle_family_mode(user.id, True)
    updated_user = repo.get_user_by_id(user.id)
    assert updated_user.family_mode is True

    # 4. Multi-tenant isolation check
    user2 = repo.create_user("test_user_2")
    all_users = repo.get_all_users()
    assert len(all_users) == 2

def test_user_repository_invalid_study_level():
    repo = UserRepository()
    user = repo.create_user("test_user")
    
    with pytest.raises(ValueError):
        repo.update_study_level(user.id, "nivel_inventado")

def test_habit_repository_upsert():
    user_repo = UserRepository()
    habit_repo = HabitRepository()
    
    user = user_repo.create_user("habit_tester")
    today = date.today()
    
    # Insert new habit
    habit = Habit(
        id=None, user_id=user.id, date=today,
        bible_reading=True, prayer=False, meditation=True
    )
    saved_habit = habit_repo.save_habit(habit)
    assert saved_habit.id is not None
    
    # Update existing habit (upsert)
    saved_habit.prayer = True
    saved_habit.notes = "Testing notes"
    habit_repo.save_habit(saved_habit)
    
    # Verify update
    fetched_habit = habit_repo.get_habit(user.id, today)
    assert fetched_habit is not None
    assert fetched_habit.prayer is True
    assert fetched_habit.meditation is True
    assert fetched_habit.notes == "Testing notes"

def test_feedback_repository_status_workflow():
    user_repo = UserRepository()
    fb_repo = FeedbackRepository()
    
    user = user_repo.create_user("feedback_tester")
    
    # Create feedback
    fb = Feedback(
        id=None, user_id=user.id, type="bug",
        message="Test bug", page="Dashboard"
    )
    saved_fb = fb_repo.create(fb)
    assert saved_fb.status == "pendiente"
    
    # Get by status
    pendientes = fb_repo.get_by_status("pendiente")
    assert len(pendientes) == 1
    
    # Update status
    fb_repo.update_status(saved_fb.id, "revisado")
    
    pendientes_after = fb_repo.get_by_status("pendiente")
    assert len(pendientes_after) == 0
    
    revisados = fb_repo.get_by_status("revisado")
    assert len(revisados) == 1
