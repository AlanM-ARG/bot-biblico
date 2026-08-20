import subprocess
import os
import shutil

DIR_PDFS = "./pdfs_nuevos"
DIR_PROCESADOS = "./pdfs_procesados"
DIR_MARKDOWN = "./data_raw"
def procesar_pdf(ruta_pdf: str, directorio_salida: str) -> bool:
    """
    Convierte un PDF a Markdown utilizando PyMuPDF4LLM.
    Si el resultado está vacío (PDF escaneado), mueve el archivo a pdfs_nuevos/requiere_ocr/
    Retorna True si la conversión fue exitosa, False en caso contrario.
    """
    print(f"🚀 Iniciando extracción rápida para: {ruta_pdf}")
    os.makedirs(directorio_salida, exist_ok=True)

    try:
        import pymupdf4llm
        # Extraer el texto en formato Markdown
        md_text = pymupdf4llm.to_markdown(ruta_pdf)
        
        # --- DETECCIÓN DE PDFs ESCANEADOS ---
        md_len = len(md_text.strip())
        pdf_size_mb = os.path.getsize(ruta_pdf) / (1024 * 1024)
        
        es_escaneado = False
        if md_len < 150:
            es_escaneado = True
        elif pdf_size_mb > 2.0 and md_len < 10000:
            es_escaneado = True
            
        if es_escaneado:
            print(f"⚠️ El PDF {os.path.basename(ruta_pdf)} parece ser una imagen escaneada (Tamaño: {pdf_size_mb:.1f}MB, Texto: {md_len} chars).")
            from services.ocr_service import extraer_texto_de_pdf_escaneado
            
            # Armar la ruta de destino (mismo nombre pero .md)
            nombre_base = os.path.basename(ruta_pdf)
            nombre_sin_ext = os.path.splitext(nombre_base)[0]
            ruta_md = os.path.join(directorio_salida, f"{nombre_sin_ext}.md")
            
            exito_ocr = extraer_texto_de_pdf_escaneado(ruta_pdf, ruta_md)
            if exito_ocr:
                # Si el OCR funciona, marcamos como True para que el archivo pase a procesados/
                return True
            else:
                # Si falla (ej. Tesseract no instalado), movemos a requiere_ocr
                dir_requiere_ocr = "./pdfs_nuevos/requiere_ocr"
                os.makedirs(dir_requiere_ocr, exist_ok=True)
                
                ruta_destino = os.path.join(dir_requiere_ocr, os.path.basename(ruta_pdf))
                shutil.move(ruta_pdf, ruta_destino)
                print(f"📁 OCR local falló. PDF movido a {dir_requiere_ocr} para revisión manual.")
                return False # Retornamos False para que no se mueva a procesados
        
        # Armar la ruta de destino (mismo nombre pero .md) para el caso normal
        nombre_base = os.path.basename(ruta_pdf)
        nombre_sin_ext = os.path.splitext(nombre_base)[0]
        ruta_md = os.path.join(directorio_salida, f"{nombre_sin_ext}.md")
        
        # Guardar el archivo
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(md_text)
            
        print(f"✅ Conversión exitosa: {ruta_pdf}")
        return True
    except ImportError:
        print("❌ PyMuPDF4LLM no está instalado. Ejecutá: pip install pymupdf4llm")
        return False
    except Exception as e:
        print(f"❌ Error al procesar {ruta_pdf}: {str(e)}")
        return False


def procesar_carpeta_pdfs() -> dict:
    """
    Escanea la carpeta pdfs_nuevos/, convierte todos los PDFs a Markdown
    y los deposita en data_raw/. Los PDFs procesados se mueven a
    pdfs_nuevos/procesados/ para no reprocesarlos.

    Retorna un diccionario con estadísticas: {"exitosos": int, "fallidos": int, "total": int}
    """
    os.makedirs(DIR_PDFS, exist_ok=True)
    os.makedirs(DIR_PROCESADOS, exist_ok=True)
    os.makedirs(DIR_MARKDOWN, exist_ok=True)

    archivos_pdf = [f for f in os.listdir(DIR_PDFS) if f.lower().endswith(".pdf")]

    if not archivos_pdf:
        print("No se encontraron PDFs nuevos en la carpeta pdfs_nuevos/.")
        return {"exitosos": 0, "fallidos": 0, "total": 0}

    exitosos = 0
    fallidos = 0

    for archivo in archivos_pdf:
        ruta_completa = os.path.join(DIR_PDFS, archivo)
        print(f"Procesando PDF {exitosos + fallidos + 1}/{len(archivos_pdf)}: {archivo}")

        if procesar_pdf(ruta_completa, DIR_MARKDOWN):
            # Mover el PDF a la carpeta de procesados
            destino = os.path.join(DIR_PROCESADOS, archivo)
            shutil.move(ruta_completa, destino)
            exitosos += 1
        else:
            fallidos += 1

    print(f"Conversión finalizada: {exitosos} exitosos, {fallidos} fallidos de {len(archivos_pdf)} totales.")
    return {"exitosos": exitosos, "fallidos": fallidos, "total": len(archivos_pdf)}
