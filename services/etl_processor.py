import os
from repositories.resource_repository import ResourceRepository
from services.resource_service import ResourceService
from services.vector_service import VectorService
from services.pdf_nougat_service import procesar_carpeta_pdfs
import glob

def sincronizar_nuevos_archivos():
    """
    Realiza una Ingesta Incremental (Bajo Demanda):
    1. Convierte PDFs nuevos a Markdown (Nougat).
    2. Escanea la carpeta data_raw/.
    3. Solo vectoriza y añade a ChromaDB los archivos que no existan previamente.
    No borra la base de datos vectorial existente.
    """
    print("Iniciando Sincronización Incremental...")
    
    # 0. Pre-procesamiento: Convertir PDFs nuevos a Markdown
    try:
        stats = procesar_carpeta_pdfs()
        if stats["total"] > 0:
            print(f"Pre-ETL: {stats['exitosos']} PDFs convertidos a Markdown.")
    except Exception as e:
        print(f"Advertencia: No se pudieron procesar PDFs (Nougat): {e}")
        
    # 1. Ingestar y vectorizar solo archivos nuevos
    resource_svc = ResourceService()
    vector_svc = VectorService()
    
    archivos_procesados = 0
    search_path = os.path.join("data_raw", "**", "*.md")
    for file_path in glob.glob(search_path, recursive=True):
        try:
            # ingest_file checks DB by MD5 hash and returns existing if already ingested.
            resource = resource_svc.ingest_file(file_path)
            
            if resource and not resource.is_vectorized:
                # Vectorizar y enviar a ChromaDB
                exito = vector_svc.vectorize_resource(resource)
                if exito:
                    archivos_procesados += 1
                    print(f"Vectorizado nuevo archivo: {file_path}")
        except Exception as e:
            print(f"Error procesando {file_path}: {e}")
            
    print(f"Sincronización Incremental Finalizada. Se procesaron {archivos_procesados} recursos nuevos.")
    return True

def forzar_reprocesamiento_total():
    """
    Realiza un Hard Reset del Pipeline ETL:
    0. Convierte cualquier PDF nuevo en pdfs_nuevos/ a Markdown (Nougat).
    1. Borra el historial de archivos procesados en SQLite.
    2. Purga (elimina) todos los vectores en la colección de ChromaDB (vector_db).
    3. Re-escanea la carpeta data_raw y procesa todos los archivos desde cero.
    """
    print("Iniciando Hard Reset del Pipeline ETL...")
    
    # 0. Pre-procesamiento: Convertir PDFs nuevos a Markdown
    try:
        stats = procesar_carpeta_pdfs()
        if stats["total"] > 0:
            print(f"Pre-ETL: {stats['exitosos']} PDFs convertidos a Markdown.")
    except Exception as e:
        print(f"Advertencia: No se pudieron procesar PDFs (Nougat): {e}")
    
    # 1. Limpiar SQLite
    repo = ResourceRepository()
    repo.delete_all()
    print("Tabla de recursos en SQLite purgada.")
    
    # 2. Purgar Colección de ChromaDB (usando VectorService)
    vector_svc = VectorService()
    try:
        vector_svc.client.delete_collection(name="biblico_collection")
        print("Colección de vectores eliminada correctamente.")
    except Exception as e:
        print(f"La colección no existía o no se pudo borrar: {e}")
    
    # Recrear la colección vacía
    vector_svc.collection = vector_svc.client.get_or_create_collection(name="biblico_collection")
    print("Colección de vectores recreada y lista.")
    
    # 3. Reingestar todos los archivos .md en data_raw/
    resource_svc = ResourceService()
    
    archivos_procesados = 0
    fragmentos_totales = 0
    
    # Buscar todos los md (incluyendo subcarpetas si las hay, aunque iteramos de forma simple)
    search_path = os.path.join("data_raw", "**", "*.md")
    for file_path in glob.glob(search_path, recursive=True):
        print(f"Procesando: {file_path}")
        try:
            # Ingestar archivo a SQLite (ResourceService también extrae metadatos y revisa reglas de IA)
            resource = resource_svc.ingest_file(file_path)
            
            if resource and not resource.is_vectorized:
                # Vectorizar y enviar a ChromaDB
                exito = vector_svc.vectorize_resource(resource)
                if exito:
                    archivos_procesados += 1
        except Exception as e:
            print(f"Error procesando {file_path}: {e}")
            
    print(f"Hard Reset Finalizado. Se procesaron y vectorizaron {archivos_procesados} recursos nuevos.")
    return True
