import os
import sys
from pathlib import Path

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.resource_service import ResourceService
from services.vector_service import VectorService

def ingest_directory(directory_path, default_category="general"):
    print(f"Ingesting directory: {directory_path}")
    resource_svc = ResourceService()
    vector_svc = VectorService()
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                print(f"Processing: {file_path}")
                
                # Infer metadata from path or filename
                inferred_category = default_category
                inferred_book = "General"
                
                path_parts = Path(file_path).parts
                lower_name = file.lower()
                
                if "9marcas" in lower_name or "9m" in lower_name:
                    inferred_category = "9marcas"
                elif "inductivo" in lower_name:
                    inferred_category = "metodo_inductivo"
                elif "credos" in lower_name or "confesiones" in lower_name:
                    inferred_category = "credo"
                elif "versiones" in lower_name or "biblia" in lower_name:
                    inferred_category = "biblia"
                    
                for part in path_parts:
                    if part.lower() in ["comentarios", "commentaries"]:
                        inferred_category = "comentario"
                    elif part.lower() == "9marcas":
                        inferred_category = "9marcas"

                # Check if it has frontmatter
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                if not content.startswith("---"):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(f"---\ncategory: \"{inferred_category}\"\nresource_type: \"documento\"\nbook: \"{inferred_book}\"\n---\n\n")
                        f.write(content)
                else:
                    # Parse existing YAML to see if we need to fix "general"
                    # For simplicity, if it's "general" and we inferred something better, we could replace it
                    # But if it already has a frontmatter, we trust it or assume the user will manually fix it
                    pass
                        
                # 1. Ingest
                resource = resource_svc.ingest_file(file_path)
                if resource:
                    # 2. Vectorize
                    success = vector_svc.vectorize_resource(resource)
                    if success:
                        print(f"[OK] Ingested and vectorized: {file.name if hasattr(file, 'name') else file}")
                    else:
                        print(f"[FAIL] Failed to vectorize: {file.name if hasattr(file, 'name') else file}")

if __name__ == "__main__":
    raw_dir = os.path.join(os.path.dirname(__file__), '..', 'data_raw')
    if os.path.exists(raw_dir):
        # Specific ingest for the main document
        main_doc = os.path.join(raw_dir, 'apreciacion_de_iglesia.md')
        if os.path.exists(main_doc):
            with open(main_doc, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.startswith("---"):
                with open(main_doc, "w", encoding="utf-8") as f:
                    f.write("---\ncategory: \"doctrina_local\"\nresource_type: \"lente_hermeneutico\"\n---\n\n")
                    f.write(content)
                    
            resource_svc = ResourceService()
            vector_svc = VectorService()
            res = resource_svc.ingest_file(main_doc)
            if res:
                vector_svc.vectorize_resource(res)
                print(f"[OK] Ingested and vectorized primary anchor: apreciacion_de_iglesia.md")
                
        # Ingest Credos
        credos_dir = os.path.join(raw_dir, 'Credos y Confesiones')
        if os.path.exists(credos_dir):
            ingest_directory(credos_dir, "credo")
            
    else:
        print(f"Directory {raw_dir} does not exist.")
    print("Done.")
