import pytest
from datetime import date, timedelta
from utils.ui_helpers import calculate_grace_score, generate_heatmap_data, get_prayer_wall_static_data
from models.habit import Habit

def test_calculate_grace_score():
    # Null case
    assert calculate_grace_score(None) == 0
    
    # Empty case
    habit_empty = Habit(id=1, user_id=1, date=date.today())
    assert calculate_grace_score(habit_empty) == 0
    
    # Partial case
    habit_partial = Habit(id=1, user_id=1, date=date.today(), bible_reading=True, prayer=True)
    assert calculate_grace_score(habit_partial) == 2
    
    # Full case
    habit_full = Habit(
        id=1, user_id=1, date=date.today(), 
        bible_reading=True, prayer=True, meditation=True, family_worship=True
    )
    assert calculate_grace_score(habit_full) == 4

def test_generate_heatmap_data_fills_gaps():
    today = date(2026, 8, 14)
    yesterday = today - timedelta(days=1)
    
    # Only 1 habit recorded
    habits = [
        Habit(id=1, user_id=1, date=yesterday, bible_reading=True)
    ]
    
    # Generate for 3 days
    heatmap = generate_heatmap_data(habits, end_date=today, days_back=3)
    
    assert len(heatmap) == 3
    assert heatmap[today.isoformat()] == 0        # No habit recorded
    assert heatmap[yesterday.isoformat()] == 1    # 1 discipline recorded
    assert heatmap[(today - timedelta(days=2)).isoformat()] == 0 # No habit recorded

def test_get_prayer_wall_static_data():
    data = get_prayer_wall_static_data()
    assert len(data) == 4
    assert "Familia" in [item["category"] for item in data]
