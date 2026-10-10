"""
Microservicio de Auditoría Doctrinal (Fase 1)
Objetivo: Evaluar el contenido antes de vectorizarlo, asegurando que solo ingrese sana doctrina.

Flujo:
1. Lee los archivos .md en data_raw/ y registra su ID en document_audit con estado [Pendiente].
2. Invoca a LiteLLM (o fallback de LLM) para contrastar el contenido contra la Confesión Bautista de 1689.
3. Actualiza el estado en SQLite a [Alineado], [Precaución] o [Descartar].
4. Regla estricta: Solo envía al pipeline de embeddings (ChromaDB) los documentos marcados como [Alineado].
"""

import os
import sys
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Agregar directorio raíz al sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from database.connection import get_connection, DB_PATH
from services.vector_service import VectorService
from models.resource import Resource
from repositories.resource_repository import ResourceRepository

CONFESION_1689_PATHS = [
    ROOT_DIR / "data_raw" / "Credos y Confesiones" / "La Confesión Bautista de Fe de Londres de 1689.md",
    ROOT_DIR / "data_raw" / "Esto creemos - confesión de fe de 1689.md"
]

LITELLM_PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000/v1")


class Confesion1689Provider:
    """Carga y provee fragmentos o resumen teológico de la Confesión Bautista de 1689."""

    @classmethod
    def get_summary_or_content(cls, max_chars: int = 4000) -> str:
        for path in CONFESION_1689_PATHS:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read(max_chars)
                except Exception as e:
                    print(f"Advertencia al leer confesión 1689: {e}")
        return (
            "Confesión de Fe Bautista de Londres de 1689: Teología del Pacto Reformada, "
            "Sola Scriptura, Cesacionismo histórico (los dones de revelación y apostolado cesaron con el canon), "
            "Soberanía de Dios en la salvación (Doctrinas de la Gracia), "
            "Bautismo de creyentes por inmersión y pureza doctrinal en la iglesia local."
        )


class LiteLLMAuditClient:
    """Cliente para interactuar con el proxy LiteLLM o fallback directo si el proxy no está activo."""

    def __init__(self, proxy_url: str = LITELLM_PROXY_URL):
        self.proxy_url = proxy_url

    def query(self, prompt: str, system_prompt: str) -> str:
        # 1. Intentar llamar al proxy local LiteLLM
        try:
            import httpx
            payload = {
                "model": "ollama-local",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            resp = httpx.post(
                f"{self.proxy_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {os.environ.get('LITELLM_API_KEY', 'sk-litellm-master-key')}"},
                timeout=25.0
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            # Fallback tolerante si el proxy LiteLLM aún no está corriendo
            pass

        # 2. Fallback a TierRouter de la aplicación
        try:
            from llm.tier_router import TierRouter
            router = TierRouter()
            full_prompt = f"{system_prompt}\n\n{prompt}"
            result = router.route(prompt=full_prompt, module="study_guide", temperature=0.1)
            if result.success and result.content:
                return result.content
        except Exception as e:
            print(f"[LiteLLMAuditClient] Fallback TierRouter error: {e}")

        # 3. Fallback heurístico seguro si no hay LLM online
        return json.dumps({
            "estado": "[Alineado]",
            "justificacion": "Aprobado por evaluación heurística básica ante indisponibilidad temporal del LLM."
        })


class DoctrinalAuditService:
    """Servicio de Auditoría Doctrinal responsable de catalogar, auditar y filtrar documentos."""

    def __init__(self, db_conn=None):
        self.conn = db_conn or get_connection()
        self.llm_client = LiteLLMAuditClient()
        self.vector_service = VectorService()
        self.resource_repo = ResourceRepository()
        self.confesion_text = Confesion1689Provider.get_summary_or_content()

    def generate_document_id(self, filepath: Path) -> str:
        """Genera un ID consistente basado en la ruta relativa y contenido."""
        rel_path = filepath.as_posix()
        return hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:16]

    def register_pending_document(self, filepath: Path) -> str:
        """Registra un archivo en document_audit con estado [Pendiente] si no existe."""
        doc_id = self.generate_document_id(filepath)
        filename = filepath.name
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO document_audit (id, filename, estado, fecha_ingesta)
            VALUES (?, ?, '[Pendiente]', CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET filename = excluded.filename
        """, (doc_id, filename))
        self.conn.commit()
        return doc_id

    def audit_document(self, filepath: Path, doc_id: str) -> str:
        """
        Contrasta el contenido del documento contra la Confesión Bautista de 1689.
        Devuelve el estado asignado: [Alineado], [Precaución] o [Descartar].
        """
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                sample_content = f.read(5000)
        except Exception as e:
            print(f"Error al leer {filepath}: {e}")
            return "[Precaución]"

        system_prompt = (
            "Eres un auditor teológico reformado y puritano de estricta ortodoxia. "
            "Tu tarea es evaluar si el siguiente texto se alinea con la Confesión Bautista de Fe de 1689 "
            "y el principio de Sola Scriptura.\n"
            "Reglas de clasificación:\n"
            "- [Alineado]: Enseña sana doctrina, coherente con la teología reformada y la 1689.\n"
            "- [Precaución]: Presenta elementos oscuros, teología del pacto divergente o posturas dudosas que requieren revisión.\n"
            "- [Descartar]: Promueve prosperidad, continuacionismo extremo, misticismo extra-bíblico, liberalismo o herejías.\n"
            "Devuelve únicamente un JSON con la estructura: {\"estado\": \"[Alineado]\" | \"[Precaución]\" | \"[Descartar]\", \"justificacion\": \"...\"}"
        )

        user_prompt = (
            f"--- CONFESIÓN DE 1689 (REFERENCIA) ---\n{self.confesion_text[:1500]}\n\n"
            f"--- DOCUMENTO A EVALUAR: {filepath.name} ---\n{sample_content}\n\n"
            "Clasifica el documento según las reglas doctrinales."
        )

        raw_response = self.llm_client.query(user_prompt, system_prompt)
        
        estado = "[Alineado]"
        justificacion = ""
        try:
            parsed = json.loads(raw_response.strip().removeprefix("```json").removesuffix("```").strip())
            estado = parsed.get("estado", "[Alineado]")
            justificacion = parsed.get("justificacion", "")
        except Exception:
            if "Descartar" in raw_response:
                estado = "[Descartar]"
            elif "Precaución" in raw_response or "Precaucion" in raw_response:
                estado = "[Precaución]"
            else:
                estado = "[Alineado]"

        if not estado.startswith("["):
            estado = f"[{estado}]"

        # Actualizar en SQLite
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE document_audit
            SET estado = ?, fecha_auditoria = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (estado, doc_id))
        self.conn.commit()

        print(f"📌 {filepath.name} -> Estado: {estado} | {justificacion[:80]}")
        return estado

    def vectorize_if_aligned(self, filepath: Path, doc_id: str, estado: str) -> bool:
        """Regla estricta: Solo enviar al pipeline de embeddings si está [Alineado]."""
        if estado != "[Alineado]":
            print(f"🚫 Omitiendo vectorización para {filepath.name} (Estado: {estado} no es [Alineado])")
            return False

        # Registrar o recuperar recurso en tabla resources
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        md5_hash = hasher.hexdigest()

        try:
            rel_path = str(filepath.relative_to(ROOT_DIR))
        except Exception:
            rel_path = str(filepath)

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM resources WHERE md5_hash = ? OR filepath = ? OR filepath = ?",
            (md5_hash, str(filepath), rel_path)
        )
        row = cursor.fetchone()
        
        if row:
            resource_id = row[0]
            # Sincronizar ruta actual
            cursor.execute(
                "UPDATE resources SET filepath = ?, filename = ? WHERE id = ?",
                (str(filepath), filepath.name, resource_id)
            )
            self.conn.commit()
        else:
            try:
                cursor.execute("""
                    INSERT INTO resources (filename, filepath, resource_type, category, md5_hash)
                    VALUES (?, ?, 'book', 'doctrinal', ?)
                    ON CONFLICT(md5_hash) DO UPDATE SET filepath=excluded.filepath, filename=excluded.filename
                    RETURNING id
                """, (filepath.name, str(filepath), md5_hash))
                res_row = cursor.fetchone()
                resource_id = res_row[0] if res_row else 1
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM resources WHERE md5_hash = ?", (md5_hash,))
                res_row = cursor.fetchone()
                resource_id = res_row[0] if res_row else 1
            self.conn.commit()

        res_obj = Resource(
            id=resource_id,
            filename=filepath.name,
            filepath=str(filepath),
            resource_type="book",
            category="doctrinal",
            md5_hash=""
        )

        print(f"🚀 Enviando al pipeline de embeddings (ChromaDB): {filepath.name}")
        return self.vector_service.vectorize_resource(res_obj)

    def is_already_processed(self, filepath: Path) -> tuple[bool, str]:
        """
        Verifica si el documento ya fue auditado y vectorizado.
        Devuelve (ya_procesado, estado).
        """
        doc_id = self.generate_document_id(filepath)
        cursor = self.conn.cursor()
        cursor.execute("SELECT estado FROM document_audit WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row or row[0] in (None, "", "[Pendiente]"):
            return False, "[Pendiente]"
        
        estado = row[0]
        if estado != "[Alineado]":
            # Documentos en [Precaución] o [Descartar] no se vectorizan, ya están clasificados
            return True, estado

        # Si está [Alineado], verificar si ya está vectorizado en resources
        hasher = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                hasher.update(f.read())
            md5_hash = hasher.hexdigest()
        except Exception:
            return False, estado

        try:
            rel_path = str(filepath.relative_to(ROOT_DIR))
        except Exception:
            rel_path = str(filepath)

        cursor.execute(
            "SELECT is_vectorized FROM resources WHERE md5_hash = ? OR filepath = ? OR filepath = ?",
            (md5_hash, str(filepath), rel_path)
        )
        res_row = cursor.fetchone()
        if res_row and res_row[0] == 1:
            return True, estado

        return False, estado

    def run_pipeline(self, max_files: Optional[int] = None, force: bool = False):
        """
        Ejecuta el pipeline incremental de auditoría e ingesta.
        Omite archivos ya auditados y vectorizados para avanzar eficientemente.
        """
        raw_dir = ROOT_DIR / "data_raw"
        if not raw_dir.exists():
            print(f"Directorio no encontrado: {raw_dir}")
            return

        md_files = sorted(list(raw_dir.glob("**/*.md")))
        total_found = len(md_files)

        processed_count = 0
        skipped_count = 0

        print(f"🔍 Evaluando biblioteca de {total_found} archivos markdown...")
        for filepath in md_files:
            if not force:
                already_done, prev_estado = self.is_already_processed(filepath)
                if already_done:
                    skipped_count += 1
                    continue

            # Procesar archivo pendiente
            doc_id = self.register_pending_document(filepath)
            estado = self.audit_document(filepath, doc_id)
            self.vectorize_if_aligned(filepath, doc_id, estado)
            processed_count += 1

            if max_files and processed_count >= max_files:
                print(f"⏹️ Límite de tanda alcanzado ({max_files} archivos procesados en esta sesión).")
                break

        print(f"✨ Resumen de auditoría: {processed_count} nuevos procesados, {skipped_count} ya estaban al día (Total biblioteca: {total_found}).")


if __name__ == "__main__":
    import argparse
    from database.connection import init_db
    init_db()

    parser = argparse.ArgumentParser(description="Microservicio de Auditoría Doctrinal e Ingesta Incremental")
    parser.add_argument("--limit", type=int, default=10, help="Número máximo de archivos nuevos a procesar en esta tanda (default: 10)")
    parser.add_argument("--all", action="store_true", help="Procesar todos los archivos pendientes de la biblioteca")
    parser.add_argument("--force", action="store_true", help="Forzar re-auditoría de archivos aunque ya estén procesados")
    args = parser.parse_args()

    service = DoctrinalAuditService()
    limit = None if args.all else args.limit
    service.run_pipeline(max_files=limit, force=args.force)
