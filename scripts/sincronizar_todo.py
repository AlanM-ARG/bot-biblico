import sys
import os

# Asegurar que Python reconozca la estructura del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.etl_processor import sincronizar_nuevos_archivos

if __name__ == "__main__":
    print("=================================================================")
    print("🚀 Iniciando Sincronización Completa en Segundo Plano (Terminal)")
    print("=================================================================")
    print("Este proceso aplicará toda la lógica oficial del sistema:")
    print("1. Intentará extraer PDF con PyMuPDF4LLM")
    print("2. Si es imagen/escaneado, usará Tesseract OCR (Fallback)")
    print("3. Vectorizará e inyectará a ChromaDB (Con respiro automático)")
    print("-----------------------------------------------------------------\n")
    
    try:
        sincronizar_nuevos_archivos()
        print("\n✅ Proceso completado exitosamente.")
    except Exception as e:
        print(f"\n❌ El proceso se detuvo por un error crítico: {e}")
