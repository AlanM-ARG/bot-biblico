import os
import sys

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.bible_parser_service import BibleParserService
from services.resource_service import ResourceService
from services.vector_service import VectorService

def main():
    parser = BibleParserService()
    
    # We will only parse RVR1960 and NBLA initially for MVP speed
    versions_to_parse = ["RVR1960_vid_149.json", "NBLA_vid_103.json"]
    
    for v in versions_to_parse:
        try:
            print(f"--- Iniciando procesamiento de {v} ---")
            parser.parse_version(v)
        except Exception as e:
            print(f"Error parseando {v}: {e}")

    print("--- Fragmentación completada ---")
    
    # Optional: We could run ResourceService ingest here, but inserting 2400 chapters 
    # sequentially into ChromaDB might take a long time locally.
    # So we'll let the user decide when to ingest them via another script or UI.
    
if __name__ == "__main__":
    main()
