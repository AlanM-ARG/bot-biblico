import os
import sys
import json
import sqlite3
from pathlib import Path

# Agregar la raíz del proyecto al sys.path para importaciones
sys.path.append(str(Path(__file__).resolve().parent.parent))

from llm.tier_router import TierRouter

DB_PATH = 'biblico.db'
DATA_RAW_DIR = 'data_raw'

PROMPT_AUDITOR = """
Eres un teólogo reformado y cesacionista, comprometido estrictamente con la Confesión de Fe Bautista de 1689. 
Analiza el siguiente fragmento del libro o la biografía del autor y evalúa si contiene elementos del movimiento carismático, pentecostal, continuacionismo, o teologías afines que contradigan el cesacionismo histórico.

Clasifica el libro en una de estas tres categorías:
1. [ALINEADO]: Totalmente libre de errores carismáticos/continuacionistas.
2. [PRECAUCIÓN]: Es un autor histórico respetable (ej. puritano o reformado), pero puede tener algún punto menor debatible, o el fragmento no es concluyente.
3. [DESCARTAR]: El autor o el texto promueve abiertamente el continuacionismo, dones carismáticos modernos, profecía contemporánea o teología pentecostal.

Devuelve la respuesta ESTRICTAMENTE en formato JSON con la siguiente estructura:
{
  "categoria": "Alineado" | "Precaución" | "Descartar",
  "justificacion": "Breve explicación teológica de por qué."
}

TEXTO A ANALIZAR:
{muestra_texto}
"""

class AuditorDoctrinal:
    def __init__(self):
        self.router = TierRouter()
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    def extract_json_from_response(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        import re
        match = re.search(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
                
        categoria = "Precaución"
        justificacion = "No se pudo parsear la respuesta de la IA. Revisión manual requerida."
        
        if "ALINEADO" in text.upper() or '"Alineado"' in text:
            categoria = "Alineado"
        elif "DESCARTAR" in text.upper() or '"Descartar"' in text:
            categoria = "Descartar"
            
        return {
            "categoria": categoria,
            "justificacion": justificacion + f"\nRespuesta original: {text[:200]}"
        }

    def auditar_archivo(self, filepath: str, filename: str):
        print(f"Auditando {filename}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                muestra = f.read(4000)
        except Exception as e:
            try:
                with open(filepath, 'r', encoding='latin-1') as f:
                    muestra = f.read(4000)
            except Exception as e:
                print(f"Error leyendo {filename}: {e}")
                return None

        prompt = PROMPT_AUDITOR.replace("{muestra_texto}", muestra)
        
        try:
            # Usar tier_1 para mayor razonamiento teológico. El router ahora es síncrono.
            result_obj = self.router.route(prompt, module="study_guide")
            if not result_obj.success:
                raise Exception(result_obj.error)
                
            result = self.extract_json_from_response(result_obj.content)
            return result
            
        except Exception as e:
            print(f"Error auditando {filename} con LLM: {e}")
            return {
                "categoria": "Precaución",
                "justificacion": f"Error de API: {e}"
            }

    def run_audit_batch(self):
        cursor = self.conn.cursor()
        
        # Crear tabla si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_libros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT UNIQUE,
                autor TEXT,
                categoria TEXT,
                justificacion TEXT,
                estado_revision TEXT
            )
        """)
        self.conn.commit()
        
        raw_dir = Path(DATA_RAW_DIR)
        if not raw_dir.exists():
            print(f"Directorio {DATA_RAW_DIR} no existe.")
            return []
            
        md_files = list(raw_dir.glob('**/*.md'))
        print(f"Encontrados {len(md_files)} archivos para auditar.")
        
        auditados = []
        for md_file in md_files:
            filename = md_file.name
            
            cursor.execute("SELECT id FROM auditoria_libros WHERE titulo = ?", (filename,))
            if cursor.fetchone():
                continue # Ya existe
                
            result = self.auditar_archivo(str(md_file), filename)
            if result:
                try:
                    cursor.execute("""
                        INSERT INTO auditoria_libros (titulo, autor, categoria, justificacion, estado_revision)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        filename, 
                        "Desconocido", 
                        result['categoria'],
                        result['justificacion'],
                        'Auditado Automáticamente'
                    ))
                    self.conn.commit()
                    print(f"[{result['categoria']}] {filename}")
                    auditados.append(filename)
                    # Pausa para no saturar la API gratuita de Gemini (límite de 15 peticiones por minuto)
                    import time
                    time.sleep(4)
                except sqlite3.IntegrityError:
                    pass
                
        return auditados

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == "__main__":
    from database.connection import init_db
    init_db()
    auditor = AuditorDoctrinal()
    auditor.run_audit_batch()
