from dataclasses import dataclass
from typing import Optional

@dataclass
class CacheAudit:
    id: Optional[int]
    guide_key: str
    generated_at: str
    file_path: str
    is_stale: bool = False
    invalidated_at: Optional[str] = None
