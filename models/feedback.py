from dataclasses import dataclass
from typing import Optional

@dataclass
class Feedback:
    id: Optional[int]
    message: str
    type: str = 'sugerencia'     # 'sugerencia', 'bug', 'critica'
    user_id: Optional[int] = None
    page: Optional[str] = None
    status: str = 'pendiente'    # 'pendiente', 'revisado', 'implementado'
    created_at: Optional[str] = None
