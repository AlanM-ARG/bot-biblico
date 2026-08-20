from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: Optional[int]
    username: str
    display_name: Optional[str] = None
    study_level: str = 'principiante'  # 'principiante', 'moderado', 'complejo'
    family_mode: bool = False
    vital_context: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
