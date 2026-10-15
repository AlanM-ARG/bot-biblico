from enum import Enum
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from models.rag_response import RAGResponse


class TipoEstudio(str, Enum):
    """Tipos de estudio bíblico soportados por el motor RAG."""
    EXEGETICO = "exegetico"
    TEMATICO = "tematico"


class NivelProfundidad(str, Enum):
    """Nivel de profundidad hermenéutica del estudio (Scaffolding)."""
    BASICO = "basico"
    INDUCTIVO = "inductivo"
    PASTORAL = "pastoral"


class EstudioRequest(BaseModel):
    """
    DTO para solicitar la generación de un estudio bíblico (exegético o temático).
    Canaliza la consulta al orquestador LLM / RAG.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "tema_o_versiculo": "Romanos 8:28-30",
                "tipo_estudio": "exegetico",
                "nivel_profundidad": "inductivo",
                "lente": "Lente Inductivo",
                "texto_biblico": "Y sabemos que a los que aman a Dios, todas las cosas les ayudan a bien...",
                "user_id": 1
            }
        }
    )

    tema_o_versiculo: str = Field(
        ...,
        description="Tema a investigar (ej. 'La Justificación por la Fe') o pasaje/versículo bíblico (ej. 'Romanos 8', 'Gálatas 2:20')",
        min_length=1
    )
    tipo_estudio: TipoEstudio = Field(
        default=TipoEstudio.EXEGETICO,
        description="Tipo de estudio: 'exegetico' (analiza un pasaje/capítulo) o 'tematico' (analiza una doctrina o tema a través de las fuentes)"
    )
    nivel_profundidad: NivelProfundidad = Field(
        default=NivelProfundidad.INDUCTIVO,
        description="Nivel de profundidad hermenéutica: 'basico' (principiante), 'inductivo' (moderado, método NBEI) o 'pastoral' (complejo, análisis exhaustivo)"
    )
    lente: Optional[str] = Field(
        default="Ninguno",
        description="Lente interpretativo: 'Ninguno', 'Lente Inductivo', 'Lente Eclesiológico 9Marcas', 'Lente Histórico', '🔬 Lente Sintáctico-Gramatical'"
    )
    texto_biblico: Optional[str] = Field(
        default=None,
        description="Texto bíblico completo opcional correspondiente al pasaje para alimentar el RAG con fuente primaria directa"
    )
    user_id: Optional[int] = Field(
        default=1,
        description="ID del usuario en la base de datos para recuperar preferencias y registrar observabilidad"
    )

    @field_validator("nivel_profundidad", mode="before")
    @classmethod
    def normalizar_nivel(cls, v):
        """Mapea sinónimos o niveles anteriores (principiante/moderado/complejo) a los DTO canónicos."""
        if isinstance(v, str):
            v_norm = v.strip().lower()
            mapping = {
                "principiante": NivelProfundidad.BASICO,
                "basico": NivelProfundidad.BASICO,
                "básico": NivelProfundidad.BASICO,
                "moderado": NivelProfundidad.INDUCTIVO,
                "inductivo": NivelProfundidad.INDUCTIVO,
                "complejo": NivelProfundidad.PASTORAL,
                "pastoral": NivelProfundidad.PASTORAL,
                "avanzado": NivelProfundidad.PASTORAL
            }
            if v_norm in mapping:
                return mapping[v_norm]
        return v

    @field_validator("tipo_estudio", mode="before")
    @classmethod
    def normalizar_tipo(cls, v):
        if isinstance(v, str):
            v_norm = v.strip().lower()
            if v_norm in ("exegetico", "exegético", "exegesis", "exégesis"):
                return TipoEstudio.EXEGETICO
            if v_norm in ("tematico", "temático", "tema"):
                return TipoEstudio.TEMATICO
        return v


class EstadoRevisionEnum(str, Enum):
    """Estado doctrinal del libro evaluado según la Confesión Bautista de Londres de 1689."""
    ALINEADO = "Alineado"
    PRECAUCION = "Precaución"
    DESCARTAR = "Descartar"
    PENDIENTE = "Pendiente"


class AuditoriaItem(BaseModel):
    """
    DTO para representar un libro o documento auditado teológicamente.
    Refleja los registros de la tabla 'auditoria_libros' en SQLite.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "titulo": "Institución de la Religión Cristiana",
                "autor": "Juan Calvino",
                "estado": "Alineado",
                "justificacion": "Completamente alineado con la soteriología reformada y la Confesión de 1689.",
                "estado_revision": "Auditado y Vectorizado",
                "resource_id": 10
            }
        }
    )

    id: Optional[int] = Field(
        default=None,
        description="Identificador único del registro de auditoría en la base de datos"
    )
    titulo: str = Field(
        ...,
        description="Título de la obra, libro o recurso teológico"
    )
    autor: str = Field(
        ...,
        description="Autor o autores de la obra"
    )
    estado: EstadoRevisionEnum = Field(
        ...,
        description="Estado de alineación doctrinal según el filtro histórico de la Confesión de Fe de 1689: 'Alineado', 'Precaución', 'Descartar', 'Pendiente'"
    )
    justificacion: Optional[str] = Field(
        default=None,
        description="Justificación doctrinal del veredicto emitida por el Agente Auditor"
    )
    estado_revision: Optional[str] = Field(
        default=None,
        description="Estado técnico del procesamiento (ej. 'Auditado y Vectorizado', 'Esperando Archivo PDF')"
    )
    resource_id: Optional[int] = Field(
        default=None,
        description="ID del recurso en la tabla resources si ya fue incorporado a la biblioteca"
    )


class BacklogItem(BaseModel):
    """
    DTO para representar un ticket del backlog automático detectado por la IA.
    Refleja los registros de la tabla 'temas_pendientes' en SQLite.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "tema_o_libro": "Comentario a 2 Tesalonicenses 1",
                "motivo_necesidad": "Vacío bibliográfico detectado durante consulta exegética del usuario",
                "tipo_recurso_requerido": "Comentario expositivo reformado",
                "estado": "Pendiente",
                "prioridad": "Alta",
                "created_at": "2026-10-15 01:00:00"
            }
        }
    )

    id: Optional[int] = Field(
        default=None,
        description="Identificador único del ticket en temas_pendientes"
    )
    tema_o_libro: str = Field(
        ...,
        description="Tema o libro bíblico detectado con carencia de fuentes teológicas"
    )
    motivo_necesidad: Optional[str] = Field(
        default=None,
        description="Explicación teológica del vacío de información detectado"
    )
    tipo_recurso_requerido: Optional[str] = Field(
        default=None,
        description="Tipo de recurso sugerido para adquisición o redacción (ej. Comentario, Monografía)"
    )
    estado: Optional[str] = Field(
        default="Pendiente",
        description="Estado del ticket: 'Pendiente', 'En Proceso' o 'Completado'"
    )
    prioridad: Optional[str] = Field(
        default="Media",
        description="Prioridad de adquisición: 'Alta', 'Media' o 'Baja'"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Fecha y hora de registro del ticket en la base de datos"
    )


class ExportarPdfRequest(BaseModel):
    """
    DTO para solicitar la exportación de un estudio o texto Markdown a formato PDF imprimible.
    Reutiliza la lógica de xhtml2pdf.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "contenido_markdown": "# Estudio Exegético: Romanos 8\n\n## 1. Observación\n\nTexto de observación...",
                "titulo": "estudio_romanos_8"
            }
        }
    )

    contenido_markdown: str = Field(
        ...,
        description="Contenido en formato Markdown que se compilará a documento PDF profesional",
        min_length=1
    )
    titulo: Optional[str] = Field(
        default="estudio_biblico",
        description="Nombre sugerido para el archivo PDF descargable (sin extensión .pdf)"
    )


class HealthResponse(BaseModel):
    """DTO para el estado del servidor y conexiones."""
    status: str = Field(default="ok", description="Estado general de la API ('ok')")
    database: str = Field(..., description="Estado de la base de datos SQLite / LibSQL")
    version: str = Field(default="1.0.0", description="Versión de la API")
    total_libros_auditados: Optional[int] = Field(default=None, description="Cantidad de libros en auditoría")
    total_backlog: Optional[int] = Field(default=None, description="Cantidad de temas en backlog")
