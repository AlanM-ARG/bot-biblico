from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class Habit:
    id: Optional[int]
    user_id: int
    date: date
    bible_reading: bool = False
    prayer: bool = False
    meditation: bool = False
    family_worship: bool = False
    notes: Optional[str] = None
