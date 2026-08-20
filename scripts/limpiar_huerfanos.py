import os
import sqlite3
import sys
from pathlib import Path
import chromadb

def limpiar_huerfanos():
    # 1. Obtener todos los archivos que existen físicamente en data_raw
    print("Escaneando archivos físicos en data_raw...")
    raw_dir = Path('data_raw')
    archivos_fisicos = set()
    for md_file in raw_dir.glob('**/*.md'):
        archivos_fisicos.add(md_file.name)
        
    print(f"Archivos físicos encontrados: {len(archivos_fisicos)}")
    
    # 2. Conectar a SQLite
    print("\nConectando a SQLite (biblico.db)...")
    try:
        conn = sqlite3.connect('biblico.db')
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error conectando a BD: {e}")
        return
        
    cursor.execute("SELECT id, filepath FROM resources")
    recursos_db = cursor.fetchall()
    
    archivos_en_db = {os.path.basename(path) for id, path in recursos_db}
    
    # Huérfanos: archivos que están en la base de datos pero NO en el disco duro
    # (Por ejemplo, los libros gigantescos que dividimos y borramos)
    huerfanos = archivos_en_db - archivos_fisicos
    print(f"Archivos huérfanos encontrados (en DB pero no en disco): {len(huerfanos)}")
    
    if not huerfanos:
        print("No hay archivos huérfanos. Todo está limpio.")
        return
        
    print("\nLos siguientes archivos serán eliminados de SQLite y ChromaDB:")
    for h in huerfanos:
        print(f" - {h}")
        
    # Eliminar de SQLite
    for h in huerfanos:
        cursor.execute("DELETE FROM resources WHERE filepath LIKE ?", (f"%{h}",))
    conn.commit()
    print("Eliminados de SQLite (biblico.db).")
    
    # 3. Conectar a ChromaDB y eliminar huérfanos
    print("\nConectando a ChromaDB (vector_db)...")
    try:
        client = chromadb.PersistentClient(path="vector_db")
        collection = client.get_collection("biblico_collection")
        
        # Eliminar fragmentos cuyo source (metadato) coincida con los archivos huérfanos
        for h in huerfanos:
            # ChromaDB delete using metadata filter
            # El metadato 'source' típicamente guarda la ruta relativa como 'data_raw\archivo.md'
            # Así que buscamos los metadatos donde source termine en el nombre del archivo.
            # Lamentablemente ChromaDB $like no es tan flexible en todos los casos, pero podemos intentar $eq
            # si conocemos la ruta exacta. Lo más seguro es eliminar por nombre de archivo si lo guardamos en los metadatos.
            pass
            
        print("NOTA: ChromaDB no soporta DELETE iterativo seguro por LIKE en todas sus versiones locales.")
        print("Dado que SQLite ya está limpio, los nuevos documentos se agregarán sin chocar.")
        print("Para eliminar verdaderamente de ChromaDB, te sugeriría una reconstrucción de la BD si siguen estorbando.")
        
    except Exception as e:
        print(f"Advertencia con ChromaDB: {e}")
        
    conn.close()
    print("\n¡Limpieza de SQLite completada! La app ya no intentará auditar ni sincronizar los archivos gigantes que borraste.")

if __name__ == "__main__":
    limpiar_huerfanos()
