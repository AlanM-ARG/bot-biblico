from pdf2image import convert_from_path
import pytesseract
import os
from PIL import Image

# Desactivar el límite de seguridad de píxeles para evitar advertencias de "DecompressionBomb"
# al procesar PDFs con escaneos de altísima resolución
Image.MAX_IMAGE_PIXELS = None

# Ruta donde instalaste Tesseract (en Windows suele ser esta)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extraer_texto_de_pdf_escaneado(ruta_pdf: str, ruta_salida_md: str) -> bool:
    """
    Realiza OCR sobre un PDF que contiene únicamente imágenes.
    Retorna True si fue exitoso, False si falló.
    """
    print(f"📷 Iniciando OCR local (Tesseract) de emergencia para: {ruta_pdf}")
    
    try:
        # Convierte cada página del PDF en una imagen
        # Pasamos explícitamente la ruta de Poppler para evitar problemas de PATH en Windows
        kwargs = {'dpi': 300}
        if os.name == 'nt':
            kwargs['poppler_path'] = r'c:\Users\alan-\Bot Biblico\poppler-26.02.0\Library\bin'
        
        paginas = convert_from_path(ruta_pdf, **kwargs) # 300 dpi es ideal para OCR
        
        texto_completo = f"# Documento Escaneado: {os.path.basename(ruta_pdf)}\n\n"
        
        for i, pagina in enumerate(paginas):
            print(f"  -> Escaneando página {i + 1} de {len(paginas)}...")
            # pytesseract lee la imagen y saca el texto en español (lang='spa')
            texto_pagina = pytesseract.image_to_string(pagina, lang='spa')
            texto_completo += f"## Página {i + 1}\n\n{texto_pagina}\n\n"
            
        # Guardamos el resultado como Markdown
        with open(ruta_salida_md, "w", encoding="utf-8") as f:
            f.write(texto_completo)
            
        print(f"✅ OCR completado. Guardado en: {ruta_salida_md}")
        return True
    except Exception as e:
        print(f"❌ Error durante el OCR local: {e}")
        return False
