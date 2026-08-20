from dataclasses import dataclass
from typing import Optional

@dataclass
class Resource:
    id: Optional[int]
    filename: str
    filepath: str
    resource_type: str        # 'pdf', 'md', 'mp3', 'geojson'
    md5_hash: str
    category: str = 'general' # 'biblia_estudio', 'comentario', 'plan_lectura', 'oracion', 'inductivo', 'confesion'
    metadata_json: Optional[str] = None
    is_vectorized: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
