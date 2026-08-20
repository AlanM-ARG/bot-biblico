import pytest
from datetime import date
from models.journal import JournalEntry
from repositories.user_repository import UserRepository
from repositories.journal_repository import JournalRepository

def test_journal_repository_crud():
    user_repo = UserRepository()
    journal_repo = JournalRepository()
    
    # 1. Setup user
    user = user_repo.create_user("journal_tester")
    today = date.today()
    
    # 2. Verify empty state
    entry = journal_repo.get_entry(user.id, today)
    assert entry is None
    
    # 3. Create entry
    new_entry = JournalEntry(
        id=None,
        user_id=user.id,
        date=today,
        humiliation="Pecado de orgullo.",
        christ="Cristo es humilde.",
        practical_application="Servir a otros hoy."
    )
    saved_entry = journal_repo.save_entry(new_entry)
    
    assert saved_entry.id is not None
    assert saved_entry.humiliation == "Pecado de orgullo."
    
    # 4. Read entry
    fetched_entry = journal_repo.get_entry(user.id, today)
    assert fetched_entry is not None
    assert fetched_entry.christ == "Cristo es humilde."
    assert fetched_entry.created_at is not None
    
    # 5. Update entry (UPSERT equivalent)
    fetched_entry.humiliation = "Corregido: Orgullo y pereza."
    journal_repo.save_entry(fetched_entry)
    
    updated_entry = journal_repo.get_entry(user.id, today)
    assert updated_entry.humiliation == "Corregido: Orgullo y pereza."

def test_journal_repository_multi_tenant_isolation():
    user_repo = UserRepository()
    journal_repo = JournalRepository()
    
    user1 = user_repo.create_user("user_a")
    user2 = user_repo.create_user("user_b")
    test_date = date(2026, 8, 14)
    
    # User 1 writes journal
    journal_repo.save_entry(JournalEntry(
        id=None, user_id=user1.id, date=test_date,
        humiliation="A", christ="A", practical_application="A"
    ))
    
    # User 2 writes journal on the same date
    journal_repo.save_entry(JournalEntry(
        id=None, user_id=user2.id, date=test_date,
        humiliation="B", christ="B", practical_application="B"
    ))
    
    # Verify isolation
    entry1 = journal_repo.get_entry(user1.id, test_date)
    entry2 = journal_repo.get_entry(user2.id, test_date)
    
    assert entry1.humiliation == "A"
    assert entry2.humiliation == "B"
    assert entry1.id != entry2.id
