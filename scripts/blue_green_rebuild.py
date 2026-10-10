import os
import sys
import time
import shutil

# 1. Configurar variables de entorno antes de importar nada
os.environ["SQLITE_DB_PATH"] = "biblico_blue.db"
os.environ["CHROMA_DB_PATH"] = "vector_db_blue"

# Limpiar restos de ejecuciones anteriores si existen
if os.path.exists("biblico_blue.db"):
    os.remove("biblico_blue.db")
if os.path.exists("vector_db_blue"):
    shutil.rmtree("vector_db_blue")

# Ahora sí, importar los módulos (leerán las variables de entorno)
from database.connection import init_db
from services.etl_processor import forzar_reprocesamiento_total

def run_blue_green_rebuild():
    print("=============================================")
    print(" INICIANDO RECONSTRUCCIÓN BLUE-GREEN (ASYNC)")
    print("=============================================")
    
    # 2. Inicializar la nueva BD (biblico_blue.db)
    print("Creando esquema en biblico_blue.db...")
    init_db()
    
    # 3. Ejecutar ETL Completo
    print("Lanzando ETL Total sobre las bases de datos temporales (Blue)...")
    try:
        exito = forzar_reprocesamiento_total()
    except Exception as e:
        print(f"❌ Error durante el ETL: {e}")
        return False
        
    if not exito:
        print("❌ El ETL falló. Abortando intercambio (Swap).")
        return False
        
    # 4. El SWAP (Intercambio en caliente)
    print("=============================================")
    print(" ETL COMPLETADO. REALIZANDO SWAP (BLUE -> LIVE)")
    print("=============================================")
    
    # Manejar SQLite
    if os.path.exists("biblico_old.db"):
        os.remove("biblico_old.db")
    if os.path.exists("biblico.db"):
        os.rename("biblico.db", "biblico_old.db")
    os.rename("biblico_blue.db", "biblico.db")
    
    # Manejar ChromaDB
    if os.path.exists("vector_db_old"):
        shutil.rmtree("vector_db_old")
    if os.path.exists("vector_db"):
        os.rename("vector_db", "vector_db_old")
    os.rename("vector_db_blue", "vector_db")
    
    print("✅ Swap completado exitosamente. La aplicación ahora usará la nueva base de datos limpia.")
    print("NOTA: El servicio de RAG podría demorar 1-2 segundos en refrescar el Singleton de ChromaDB.")
    return True

if __name__ == "__main__":
    start_time = time.time()
    run_blue_green_rebuild()
    print(f"⏱️ Tiempo total: {time.time() - start_time:.2f} segundos.")
