import os
from pathlib import Path

# Set path relative to this script
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge_base"

def load_documents() -> list[str]:
    """
    Lee todos los archivos .txt y .md en la carpeta knowledge_base
    y devuelve su contenido como una lista de strings.
    """
    documents = []
    
    # Ensure dir exists
    if not KNOWLEDGE_DIR.exists():
        os.makedirs(KNOWLEDGE_DIR)
        return documents
        
    for file_path in KNOWLEDGE_DIR.iterdir():
        if file_path.is_file() and file_path.suffix in ['.txt', '.md']:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    documents.append(f"Documento: {file_path.name}\n\n{content}")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                
    return documents
