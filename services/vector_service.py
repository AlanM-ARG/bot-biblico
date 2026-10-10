import os
import re
from models.resource import Resource
from repositories.resource_repository import ResourceRepository
from repositories.cache_audit_repository import CacheAuditRepository
from core.embeddings import get_encoder
from core.vector_db import get_chroma_client, get_collection
from services.graph_service import GraphService

class VectorService:
    def __init__(self, use_ephemeral=False):
        self.repo = ResourceRepository()
        self.cache_repo = CacheAuditRepository()
        
        # Shared embedding model singleton
        self.encoder = get_encoder()
        
        # Shared ChromaDB client singleton
        if use_ephemeral:
            import chromadb
            self.client = chromadb.EphemeralClient()
            self.collection = self.client.get_or_create_collection(name="biblico_collection")
        else:
            self.client = get_chroma_client()
            self.collection = get_collection()
            
        self.graph_service = GraphService()

    def _strip_frontmatter(self, content: str) -> str:
        """Removes the YAML frontmatter from a markdown file."""
        return re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL).strip()

    def _split_by_headers(self, text: str) -> list[dict]:
        """
        Splits markdown text by headers (#, ##, ###), preserving the header hierarchy
        as metadata for each section. This is the 'semantic' layer of chunking.
        Returns a list of dicts: {"content": str, "headers": {"Tema": ..., "Seccion": ..., "Subtema": ...}}
        """
        # Pattern: match lines starting with 1-3 '#' characters
        header_pattern = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
        
        sections = []
        current_headers = {"Tema_Principal": "", "Seccion": "", "Subtema": ""}
        last_end = 0
        
        for match in header_pattern.finditer(text):
            # Save the content BEFORE this header as a section (if non-empty)
            content_before = text[last_end:match.start()].strip()
            if content_before:
                sections.append({
                    "content": content_before,
                    "headers": dict(current_headers)
                })
            
            # Update hierarchy based on header level
            level = len(match.group(1))
            header_text = match.group(2).strip()
            
            if level == 1:
                current_headers = {"Tema_Principal": header_text, "Seccion": "", "Subtema": ""}
            elif level == 2:
                current_headers["Seccion"] = header_text
                current_headers["Subtema"] = ""
            elif level == 3:
                current_headers["Subtema"] = header_text
            
            last_end = match.end()
        
        # Don't forget the last section after the final header
        remaining = text[last_end:].strip()
        if remaining:
            sections.append({
                "content": remaining,
                "headers": dict(current_headers)
            })
        
        return sections

    def chunk_text(self, text: str, max_chunk_size: int = 1000, overlap_size: int = 150) -> list[dict]:
        """
        Two-level semantic chunking:
        1. First splits by Markdown headers (#, ##, ###) to preserve logical structure.
        2. Then applies paragraph-based chunking with overlap WITHIN each section.
        
        Returns a list of dicts: {"text": str, "headers": dict}
        Each dict contains the chunk text and the header hierarchy it belongs to.
        """
        sections = self._split_by_headers(text)
        
        if not sections:
            # Fallback: no headers found, treat as single flat section
            sections = [{"content": text, "headers": {"Tema_Principal": "", "Seccion": "", "Subtema": ""}}]
        
        all_chunks = []
        
        for section in sections:
            content = section["content"]
            headers = section["headers"]
            
            # Apply paragraph-based chunking with overlap within this section
            paragraphs = content.split("\n\n")
            current_chunk_paragraphs = []
            current_length = 0
            
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                
                p_len = len(p)
                
                if current_length + p_len + (2 if current_length > 0 else 0) > max_chunk_size and current_chunk_paragraphs:
                    # Save chunk with its header metadata
                    all_chunks.append({
                        "text": "\n\n".join(current_chunk_paragraphs),
                        "headers": headers
                    })
                    
                    # Calculate overlap
                    overlap_length = 0
                    overlap_paragraphs = []
                    for prev_p in reversed(current_chunk_paragraphs):
                        if overlap_length + len(prev_p) > overlap_size and overlap_paragraphs:
                            break
                        overlap_paragraphs.insert(0, prev_p)
                        overlap_length += len(prev_p) + 2
                    
                    current_chunk_paragraphs = overlap_paragraphs + [p]
                    current_length = overlap_length + p_len
                else:
                    current_chunk_paragraphs.append(p)
                    current_length += p_len + (2 if current_length > 0 else 0)
            
            if current_chunk_paragraphs:
                all_chunks.append({
                    "text": "\n\n".join(current_chunk_paragraphs),
                    "headers": headers
                })
        
        return all_chunks

    def vectorize_resource(self, resource: Resource) -> bool:
        """
        Reads the resource file, chunks it semantically by headers,
        generates embeddings, saves to ChromaDB, and marks it as vectorized in SQLite.
        """
        if not os.path.exists(resource.filepath):
            print(f"Error: File not found: {resource.filepath}")
            return False
            
        with open(resource.filepath, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        clean_content = self._strip_frontmatter(raw_content)
        chunks = self.chunk_text(clean_content)
        
        if not chunks:
            print("No text found to chunk.")
            return False
        
        # Extract text strings for embedding
        chunk_texts = [c["text"] for c in chunks]
            
        # Generate IDs and metadata for ChromaDB (now enriched with header hierarchy)
        ids = [f"res_{resource.id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "resource_id": resource.id,
                "category": resource.category,
                "chunk_index": i,
                "tema_principal": c["headers"].get("Tema_Principal", ""),
                "seccion": c["headers"].get("Seccion", ""),
                "subtema": c["headers"].get("Subtema", "")
            } for i, c in enumerate(chunks)
        ]
        
        # Generate Embeddings
        embeddings = self.encoder.encode(chunk_texts).tolist()
        
        # Upsert to ChromaDB in very small batches with retry logic for Windows SQLite compaction
        import time
        BATCH_SIZE = 100
        for i in range(0, len(ids), BATCH_SIZE):
            intentos = 0
            while intentos < 3:
                try:
                    self.collection.upsert(
                        ids=ids[i:i+BATCH_SIZE],
                        embeddings=embeddings[i:i+BATCH_SIZE],
                        documents=chunk_texts[i:i+BATCH_SIZE],
                        metadatas=metadatas[i:i+BATCH_SIZE]
                    )
                    break
                except Exception as e:
                    intentos += 1
                    print(f"⚠️ Error de ChromaDB/SQLite. Reintentando ({intentos}/3) tras 5s... Error: {e}")
                    time.sleep(5)
                    if intentos == 3:
                        print("❌ Fallo crítico en la base de datos de vectores tras 3 intentos. Abortando este archivo.")
                        raise e
                        
            # Pausa obligatoria para permitir que el hilo de compactación limpie la memoria
            time.sleep(1.0)
            
            # Automatización del Fallback ("Respiro Profundo")
            # Cada 10 lotes (1000 fragmentos), hacemos una pausa larga de 15s para vaciar la caché por completo
            batch_num = (i // BATCH_SIZE) + 1
            if batch_num % 10 == 0:
                print(f"   [Automated Fallback] Lote {batch_num} alcanzado. Iniciando 'Respiro Profundo' de 15s para limpiar SQLite...")
                time.sleep(15.0)
        
        # Update SQLite status and invalidate cache
        if resource.id is not None:
            self.repo.mark_as_vectorized(resource.id)
            self.cache_repo.invalidate_all()
            
        print(f"✅ {resource.filename}: {len(chunks)} fragmentos semánticos vectorizados.")
        return True

    def delete_document_vectors(self, doc_identifier: str) -> bool:
        """
        Elimina todos los vectores asociados a un documento por resource_id, filename o ID.
        Utilizado para purgar automáticamente vectores cuando un documento es degradado doctrinalmente.
        """
        try:
            # 1. Intento por resource_id numérico
            try:
                res_id_int = int(doc_identifier)
                self.collection.delete(where={"resource_id": res_id_int})
                self.cache_repo.invalidate_all()
                print(f"🗑️ Chunks eliminados de ChromaDB para resource_id={res_id_int}")
                return True
            except (ValueError, Exception):
                pass

            # 2. Intento por metadato filename
            try:
                self.collection.delete(where={"filename": str(doc_identifier)})
                self.cache_repo.invalidate_all()
                print(f"🗑️ Chunks eliminados de ChromaDB para filename={doc_identifier}")
                return True
            except Exception:
                pass

            # 3. Búsqueda por coincidencia en IDs de ChromaDB
            records = self.collection.get()
            if records and "ids" in records:
                matching_ids = [cid for cid in records["ids"] if str(doc_identifier) in cid]
                if matching_ids:
                    self.collection.delete(ids=matching_ids)
                    self.cache_repo.invalidate_all()
                    print(f"🗑️ {len(matching_ids)} chunks eliminados de ChromaDB para {doc_identifier}")
                    return True

            return False
        except Exception as e:
            print(f"⚠️ Error al eliminar vectores de ChromaDB para {doc_identifier}: {e}")
            return False

