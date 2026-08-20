import markdown
from xhtml2pdf import pisa
import io

def generar_pdf_desde_markdown(texto_md):
    """
    Convierte texto Markdown a un archivo PDF en memoria.
    """
    # 1. Convertir Markdown a HTML
    html_content = markdown.markdown(texto_md, extensions=['tables', 'fenced_code'])
    
    # 2. Envolver el HTML con estilos CSS para que el PDF se vea limpio y profesional
    plantilla_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 2cm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                font-size: 13px;
                line-height: 1.6;
                color: #333333;
            }}
            h1 {{ color: #1a202c; font-size: 24px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; }}
            h2 {{ color: #2d3748; font-size: 20px; margin-top: 20px; }}
            h3 {{ color: #4a5568; font-size: 16px; }}
            p {{ margin-bottom: 15px; text-align: justify; }}
            ul, ol {{ margin-bottom: 15px; }}
            li {{ margin-bottom: 5px; }}
            blockquote {{
                border-left: 4px solid #718096;
                margin: 10px 0;
                padding-left: 15px;
                color: #4a5568;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # 3. Crear el PDF en un buffer de memoria (sin guardar en disco)
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(plantilla_html, dest=buffer)
    
    if pisa_status.err:
        return None
        
    return buffer.getvalue()
