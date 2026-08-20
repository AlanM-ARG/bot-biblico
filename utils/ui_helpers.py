from datetime import date, timedelta
from typing import List, Dict

def calculate_grace_score(habit) -> int:
    """
    Calculates a score from 0 to 4 based on completed disciplines.
    Used to color the heatmap in the UI.
    """
    if not habit:
        return 0
    
    score = 0
    if habit.bible_reading: score += 1
    if habit.prayer: score += 1
    if habit.meditation: score += 1
    if habit.family_worship: score += 1
    return score

def generate_heatmap_data(habits: List, end_date: date, days_back: int = 30) -> Dict[str, int]:
    """
    Generates a continuous dictionary of dates mapped to their grace score,
    ensuring all days are present even if no habit was recorded.
    """
    heatmap = {}
    
    # Convert list of habits into a dictionary indexed by date string for O(1) lookup
    habit_dict = {h.date.isoformat(): h for h in habits}
    
    for i in range(days_back):
        current = end_date - timedelta(days=i)
        iso_date = current.isoformat()
        
        habit = habit_dict.get(iso_date)
        heatmap[iso_date] = calculate_grace_score(habit)
        
    return heatmap

def get_prayer_wall_static_data() -> List[Dict[str, str]]:
    """
    Returns static data for the prayer wall to be rendered in Sprint 2.
    """
    return [
        {"category": "Familia", "request": "Sabiduría para liderar el devocional con Ailín."},
        {"category": "Iglesia Local", "request": "Por la predicación expositiva de este domingo."},
        {"category": "Lucha Personal", "request": "Dominio propio frente a la ansiedad laboral."},
        {"category": "Misiones", "request": "Por los hermanos perseguidos en Medio Oriente."}
    ]
