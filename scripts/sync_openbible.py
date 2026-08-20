import os
import sys
import shutil
import datetime
from pathlib import Path

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.openbible_service import OpenBibleService

def backup_existing_data(target_dir: Path, backup_dir: Path):
    if target_dir.exists():
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        print(f"Backing up {target_dir} to {backup_dir}...")
        shutil.copytree(target_dir, backup_dir)

def restore_backup(backup_dir: Path, target_dir: Path):
    if backup_dir.exists():
        if target_dir.exists():
            shutil.rmtree(target_dir)
        print(f"Restoring backup from {backup_dir} to {target_dir}...")
        shutil.copytree(backup_dir, target_dir)

def main():
    print(f"[{datetime.datetime.now()}] Iniciando Sincronización Semanal de OpenBible...")
    
    prod_dir = Path("data/openbible")
    backup_dir = Path("data/openbible_backup")
    temp_dir = Path("data/temp_openbible")
    
    # 1. Cleanup temp if exists
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
        
    try:
        # 2. Initialize service on temp directory
        service = OpenBibleService(output_dir=str(temp_dir))
        
        # 3. Perform downloads and parses
        print("Sincronizando Tópicos...")
        service.sync_topics()
        
        print("Sincronizando Referencias Cruzadas...")
        service.sync_cross_references()
        
        print("Sincronizando Datos Geográficos...")
        service.sync_geocoding()
        
        # 4. If we reach here, ETL was successful.
        print("ETL OpenBible completado en directorio temporal. Aplicando a producción...")
        
        # Backup production data
        backup_existing_data(prod_dir, backup_dir)
        
        # Swap temp to prod
        if prod_dir.exists():
            shutil.rmtree(prod_dir)
        shutil.copytree(temp_dir, prod_dir)
        
        print(f"[{datetime.datetime.now()}] [OK] Sincronización y Aplicación Exitosa.")
        
    except Exception as e:
        print(f"[{datetime.datetime.now()}] [ERROR] Error durante la sincronización: {e}")
        print("Abortando. La base de producción no fue modificada.")
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
