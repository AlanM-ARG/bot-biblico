from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class JournalEntry:
    id: Optional[int]
    user_id: int
    date: date
    humiliation: str = ""
    christ: str = ""
    practical_application: str = ""
