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


@dataclass
class FeedbackBeta:
    """Feedback explícito sobre respuestas RAG para auditoría doctrinal y auto-ajuste."""
    interaction_id: str
    rating: int = 1  # 1 (positivo/útil) o -1 (negativo/reporte)
    motivo: Optional[str] = None  # ej. 'Error Doctrinal', 'Alucinación', etc.
    comentario_libre: Optional[str] = None
    procesado: int = 0
    id: Optional[int] = None
    created_at: Optional[str] = None
