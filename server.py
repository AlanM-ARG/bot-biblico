"""
server.py - Servidor Backend FastAPI para Teos AI (Bot Bíblico)

Define la API REST técnica y estandarizada para:
1. Generación de estudios bíblicos (Exegéticos y Temáticos) canalizados al orquestador LLM / RAG.
2. Consulta de libros y recursos evaluados doctrinalmente según la Confesión 1689 (auditoria_libros).
3. Consulta y gestión del backlog automático de vacíos bibliográficos detectados por IA (temas_pendientes).
4. Exportación de guías de estudio y Markdown a documentos PDF imprimibles vía xhtml2pdf.

Este archivo genera la 'biblia técnica' en /openapi.json para la generación del frontend en React con Google AI Studio.
"""

import os
import sys
import json
import re
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from database.connection import init_db, get_connection
from schemas.api_dto import (
    TipoEstudio,
    NivelProfundidad,
    EstudioRequest,
    RAGResponse,
    EstadoRevisionEnum,
    AuditoriaItem,
    BacklogItem,
    ExportarPdfRequest,
    HealthResponse,
)
from repositories.user_repository import UserRepository
from utils.pdf_helper import generar_pdf_desde_markdown

# Servicio RAG instanciado perezosamente (Lazy Loading) para inicialización ultrarrápida del servidor
_rag_service = None

def get_rag_service():
    """Obtiene o inicializa la instancia singleton de RAGService."""
    global _rag_service
    if _rag_service is None:
        from services.rag_service import RAGService
        _rag_service = RAGService()
    return _rag_service


def export_openapi_json(output_path: str = "openapi.json"):
    """Exporta el esquema OpenAPI completo en formato JSON a disco."""
    schema = app.openapi()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"Esquema OpenAPI exportado exitosamente a: {os.path.abspath(output_path)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: asegura DB inicializada y exporta openapi.json al arrancar."""
    try:
        init_db()
    except Exception as e:
        print(f"[AVISO] Error al inicializar DB en lifespan: {e}")
    
    # Exportar openapi.json automáticamente para AI Studio
    try:
        export_openapi_json()
    except Exception as e:
        print(f"[AVISO] Error al exportar openapi.json en lifespan: {e}")
        
    yield


app = FastAPI(
    title="Teos AI - API Bíblica",
    description=(
        "Backend REST API para Teos AI: orquestación de RAG teológico, estudios inductivos/exegéticos, "
        "auditoría doctrinal histórica (Confesión de Fe Bautista de Londres 1689), backlog automático "
        "y exportación de documentos a PDF. Estandarizado para generación de frontend React en Google AI Studio."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configuración de CORS amplia para permitir integración inmediata desde cualquier cliente React (Vite, Next, AI Studio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# Endpoints de Utilidad / Salud
# =====================================================================

@app.get(
    "/",
    tags=["General"],
    summary="Información de la API",
    description="Retorna el estado general de la API e hipervínculos a la documentación técnica y OpenAPI."
)
def root():
    return {
        "app": "Teos AI - Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "status": "online"
    }


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["General"],
    summary="Verificación de Salud del Sistema",
    description="Comprueba el estado de la conexión a la base de datos SQLite y métricas básicas de registros."
)
def health_check():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM auditoria_libros")
        count_audit = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM temas_pendientes")
        count_backlog = cursor.fetchone()[0]
        
        conn.close()
        
        return HealthResponse(
            status="ok",
            database="connected",
            version="1.0.0",
            total_libros_auditados=count_audit,
            total_backlog=count_backlog
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            database=f"error: {str(e)}",
            version="1.0.0"
        )


# =====================================================================
# Endpoint 1: Generación de Estudios (Exegético vs. Temático)
# =====================================================================

@app.post(
    "/api/estudio",
    response_model=RAGResponse,
    status_code=status.HTTP_200_OK,
    tags=["Estudios Bíblicos"],
    summary="Canalizar Consulta de Estudio Bíblico",
    description=(
        "Canaliza la consulta al orquestador LLM actual. Soporta estudios exegéticos por versículo/capítulo "
        "y estudios temáticos de doctrinas. Ajusta el andamiaje (scaffolding) al nivel de profundidad "
        "solicitado (básico, inductivo o pastoral)."
    )
)
def generar_estudio(request: EstudioRequest):
    try:
        user_repo = UserRepository()
        user_id = request.user_id or 1
        user = user_repo.get_user_by_id(user_id)
        
        # Si el usuario no existe, asegurar usuario por defecto para no romper el pipeline
        if not user:
            user = user_repo.get_user_by_id(1)
            if not user:
                user = user_repo.create_user("usuario_api", "Usuario API")
            user_id = user.id

        # Mapear nivel de profundidad al modelo interno de andamiaje
        level_map = {
            NivelProfundidad.BASICO: "principiante",
            NivelProfundidad.INDUCTIVO: "moderado",
            NivelProfundidad.PASTORAL: "complejo"
        }
        mapped_level = level_map.get(request.nivel_profundidad, "moderado")
        
        # Sincronizar nivel en la preferencia del usuario si difiere
        if user.study_level != mapped_level:
            try:
                user_repo.update_study_level(user_id, mapped_level)
            except Exception:
                pass

        # Lente Sintáctico-Gramatical especializado
        if request.lente == "🔬 Lente Sintáctico-Gramatical" and request.texto_biblico:
            from services.propositional_service import PropositionalService
            prop_svc = PropositionalService()
            analisis = prop_svc.analyze_with_lens(
                bible_text=request.texto_biblico,
                book_name=request.tema_o_versiculo,
                user_level=mapped_level
            )
            return RAGResponse(
                content=analisis,
                sources_used=["Análisis Sintáctico-Gramatical Proposicional"],
                fallback_no_rag=False,
                recommended_resources=[]
            )

        rag = get_rag_service()

        if request.tipo_estudio == TipoEstudio.EXEGETICO:
            response = rag.generate_study_guide(
                user_id=user_id,
                chapter=request.tema_o_versiculo,
                lens=request.lente or "Ninguno",
                bible_text=request.texto_biblico
            )
            return response
            
        elif request.tipo_estudio == TipoEstudio.TEMATICO:
            response = rag.generate_topic_study(
                user_id=user_id,
                topic=request.tema_o_versiculo
            )
            return response

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de estudio '{request.tipo_estudio}' no reconocido."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el orquestador LLM: {str(e)}"
        )


# =====================================================================
# Endpoint 2: Auditoría Doctrinal de Libros
# =====================================================================

@app.get(
    "/api/auditoria",
    response_model=List[AuditoriaItem],
    status_code=status.HTTP_200_OK,
    tags=["Biblioteca y Auditoría"],
    summary="Listar Registros de Auditoría Doctrinal",
    description=(
        "Consulta la tabla 'auditoria_libros' en SQLite para obtener las obras teológicas y su veredicto "
        "doctrinal según la Confesión Bautista de 1689 (Alineado, Precaución, Descartar, Pendiente)."
    )
)
def obtener_auditoria(
    estado: Optional[EstadoRevisionEnum] = Query(
        None,
        description="Filtrar por estado de revisión doctrinal: 'Alineado', 'Precaución', 'Descartar', 'Pendiente'"
    ),
    search: Optional[str] = Query(
        None,
        description="Buscar coincidencias en título o autor del libro"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Cantidad máxima de registros a retornar"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Desplazamiento para paginación de resultados"
    )
):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = (
            "SELECT id, titulo, autor, categoria AS estado, justificacion, estado_revision, resource_id "
            "FROM auditoria_libros WHERE 1=1"
        )
        params = []
        
        if estado:
            query += " AND categoria = ?"
            params.append(estado.value if hasattr(estado, "value") else str(estado))
            
        if search and search.strip():
            query += " AND (titulo LIKE ? OR autor LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term])
            
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        items = [AuditoriaItem(**dict(r)) for r in rows]
        return items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar auditoria_libros: {str(e)}"
        )


# =====================================================================
# Endpoint 3: Backlog Automático de Temas Faltantes
# =====================================================================

@app.get(
    "/api/backlog",
    response_model=List[BacklogItem],
    status_code=status.HTTP_200_OK,
    tags=["Biblioteca y Auditoría"],
    summary="Listar Tickets de Vacíos Bibliográficos (Backlog)",
    description=(
        "Consulta la tabla 'temas_pendientes' en SQLite donde el motor RAG registra proactivamente "
        "los vacíos de información o carencias documentales detectadas durante las consultas."
    )
)
def obtener_backlog(
    estado: Optional[str] = Query(
        None,
        description="Filtrar por estado del ticket (ej. 'Pendiente', 'Completado')"
    ),
    prioridad: Optional[str] = Query(
        None,
        description="Filtrar por prioridad (ej. 'Alta', 'Media', 'Baja')"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Cantidad máxima de tickets a retornar"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Desplazamiento para paginación"
    )
):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = (
            "SELECT id, tema_o_libro, motivo_necesidad, tipo_recurso_requerido, estado, prioridad, created_at "
            "FROM temas_pendientes WHERE 1=1"
        )
        params = []
        
        if estado and estado.strip():
            query += " AND estado = ?"
            params.append(estado.strip())
            
        if prioridad and prioridad.strip():
            query += " AND prioridad = ?"
            params.append(prioridad.strip())
            
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [BacklogItem(**dict(r)) for r in rows]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar temas_pendientes: {str(e)}"
        )


# =====================================================================
# Endpoint 4: Exportación de PDF (xhtml2pdf)
# =====================================================================

@app.post(
    "/api/exportar-pdf",
    status_code=status.HTTP_200_OK,
    tags=["Exportación y Reportes"],
    summary="Exportar Markdown a Documento PDF",
    description=(
        "Recibe un contenido en formato Markdown y reutiliza la biblioteca xhtml2pdf "
        "para retornar directamente los bytes del archivo PDF listo para imprimir o descargar."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Archivo binario PDF generado listo para visualización o descarga."
        },
        400: {
            "description": "El texto provisto no pudo ser transformado a PDF."
        }
    }
)
def exportar_pdf(request: ExportarPdfRequest):
    try:
        texto_md = request.contenido_markdown
        if not texto_md or not texto_md.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El contenido Markdown provisto está vacío."
            )

        pdf_bytes = generar_pdf_desde_markdown(texto_md)
        if not pdf_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error al procesar y compilar el texto Markdown a PDF vía xhtml2pdf."
            )

        # Sanitizar nombre de archivo para cabecera HTTP
        titulo_base = request.titulo or "estudio_biblico"
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', titulo_base.strip().lower())
        if not safe_filename.endswith(".pdf"):
            safe_filename += ".pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Content-Length": str(len(pdf_bytes))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la exportación a PDF: {str(e)}"
        )


# =====================================================================
# Exportador CLI y Ejecución Principal
# =====================================================================

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Teos AI Backend Server & OpenAPI Tool")
    parser.add_argument("--export-openapi", action="store_true", help="Exportar esquema openapi.json a disco y salir")
    parser.add_argument("--port", type=int, default=8000, help="Puerto de escucha (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host de escucha (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.export_openapi:
        export_openapi_json()
        sys.exit(0)

    # Por defecto, exportar el esquema openapi.json antes de iniciar
    export_openapi_json()

    print(f"Iniciando servidor FastAPI Teos AI en http://{args.host}:{args.port}")
    print(f"Documentación Swagger interactiva: http://localhost:{args.port}/docs")
    print(f"Esquema OpenAPI JSON: http://localhost:{args.port}/openapi.json")
    
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
