import os
import hashlib
import re
import json
from models.resource import Resource
from repositories.resource_repository import ResourceRepository
from services.audio_service import AudioService

class ResourceService:
    def __init__(self):
        self.repo = ResourceRepository()

    def calculate_md5(self, file_path: str) -> str:
        """Calculate the MD5 hash of a file to prevent duplicates."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def parse_frontmatter(self, file_path: str) -> dict:
        """
        Parses YAML-like frontmatter from a markdown file.
        Returns a dictionary of metadata. Defaults to general category if missing.
        """
        metadata = {
            "category": "general",
            "resource_type": "documento"
        }
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Regex to match frontmatter between --- and ---
                match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if match:
                    frontmatter = match.group(1)
                    for line in frontmatter.split("\n"):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            metadata[key] = val
        except Exception as e:
            print(f"Error parsing frontmatter for {file_path}: {e}")
            
        return metadata

    def ingest_file(self, file_path: str) -> Resource | None:
        """
        Ingests a file if it hasn't been ingested already.
        Returns the Resource object if ingested or already exists, None on error.
        """
        if not os.path.exists(file_path):
            return None
            
        md5_hash = self.calculate_md5(file_path)
        
        # Check for duplicates
        existing = self.repo.get_by_hash(md5_hash)
        if existing:
            print(f"File already ingested: {file_path} (Hash: {md5_hash})")
            return existing
            
        # --- Audio Handling ---
        is_audio = file_path.lower().endswith((".mp3", ".wav", ".m4a"))
        if is_audio:
            print(f"Detectado archivo de audio. Iniciando transcripción Whisper...")
            audio_svc = AudioService()
            transcript = audio_svc.transcribe(file_path)
            
            # Create a markdown file from the transcript
            os.makedirs("data/processed", exist_ok=True)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            md_path = f"data/processed/{base_name}.md"
            
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("---\n")
                f.write("category: \"predicacion_local\"\n")
                f.write("resource_type: \"audio_transcrito\"\n")
                f.write("---\n\n")
                f.write(f"# Transcripción: {base_name}\n\n")
                f.write(transcript)
                
            # Now ingest the new markdown file instead of the audio file directly, 
            # but we keep the audio's MD5 hash to prevent re-transcribing the same audio.
            metadata = {
                "category": "predicacion_local",
                "resource_type": "audio_transcrito",
                "original_audio": file_path
            }
            filename = os.path.basename(md_path)
            actual_filepath = md_path
        else:
            # --- Text/Markdown Handling ---
            metadata = self.parse_frontmatter(file_path)
            filename = os.path.basename(file_path)
            actual_filepath = file_path
    
        new_resource = Resource(
            id=None,
            filename=filename,
            filepath=actual_filepath,
            resource_type=metadata.get("resource_type", "documento"),
            category=metadata.get("category", "general"),
            md5_hash=md5_hash,
            metadata_json=json.dumps(metadata)
        )
        
        result = self.repo.create(new_resource)
        
        # Self-Improving RAG ETL Trigger
        if not is_audio:
            self.extract_and_save_rules(actual_filepath, metadata)
            
        return result

    def extract_and_save_rules(self, file_path: str, metadata: dict):
        """
        Uses LLM to extract exegetical rules/methodology from the document
        and appends them to data/reglas_hermeneuticas.json.
        """
        if "inductivo" not in file_path.lower() and "hermeneutica" not in file_path.lower() and "teologico" not in file_path.lower():
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            content_sample = content[:15000] 
            
            from llm.tier_router import TierRouter
            router = TierRouter()
            
            prompt = f"""Analiza el siguiente texto de un manual de estudio bíblico o recurso teológico.
Extrae explícitamente las "Reglas Hermenéuticas", "Pasos Metodológicos" o "Preguntas Inductivas" que el autor propone para estudiar la Biblia.
Formatea tu respuesta ÚNICAMENTE como un array JSON válido de strings. Ejemplo: ["Preguntar quién, qué, cuándo", "Identificar el contexto histórico"].
Si no hay reglas explícitas o claras, devuelve []. No uses markdown de bloques de código.

Texto:
{content_sample}
"""
            result = router.route(prompt=prompt, module="etl_classify", temperature=0.1)
            if not result.success or not result.content:
                return
            response = result.content.replace("```json", "").replace("```", "").strip()
            
            new_rules = json.loads(response)
            
            if not new_rules:
                return
                
            rules_path = "data/reglas_hermeneuticas.json"
            existing_rules = []
            if os.path.exists(rules_path):
                try:
                    with open(rules_path, "r", encoding="utf-8") as f:
                        existing_rules = json.load(f)
                except:
                    existing_rules = []
                    
            for rule in new_rules:
                if rule not in existing_rules:
                    existing_rules.append(rule)
                    
            # Control de Límite (Token Overflow)
            if len(existing_rules) > 15:
                existing_rules = existing_rules[-15:]
                    
            os.makedirs("data", exist_ok=True)
            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(existing_rules, f, ensure_ascii=False, indent=2)
                
            print(f"[{file_path}] Reglas extraídas e inyectadas al RAG Auto-Evolutivo: {len(new_rules)}")
            
        except Exception as e:
            print(f"Error extrayendo reglas de {file_path}: {e}")

