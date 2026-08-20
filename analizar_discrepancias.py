import os
from pathlib import Path

procesados_dir = Path("pdfs_procesados")
data_raw_dir = Path("data_raw")

print("Analizando discrepancias entre PDFs procesados y sus archivos .md...\n")

discrepancias = []

for pdf_file in procesados_dir.glob("*.pdf"):
    md_file = data_raw_dir / (pdf_file.stem + ".md")
    
    if md_file.exists():
        pdf_size_mb = pdf_file.stat().st_size / (1024 * 1024)
        # Quitar los espacios en blanco para contar la verdadera densidad del texto
        md_text = md_file.read_text(encoding="utf-8").strip()
        md_size_kb = len(md_text.encode("utf-8")) / 1024
        
        # Criterio: Si el PDF pesa más de 2MB pero el texto extraído es menor a 10KB
        if pdf_size_mb > 2.0 and md_size_kb < 10.0:
            discrepancias.append(pdf_file)

if not discrepancias:
    print("No se encontraron archivos sospechosos.")
else:
    print(f"Moviendo {len(discrepancias)} archivos sospechosos a pdfs_nuevos/ y eliminando sus .md...")
    import shutil
    for pdf_file in discrepancias:
        # Rutas
        md_file = data_raw_dir / (pdf_file.stem + ".md")
        destino_pdf = Path("pdfs_nuevos") / pdf_file.name
        
        safe_name = pdf_file.name.encode('ascii', 'ignore').decode('ascii')
        print(f" -> Reciclando: {safe_name}")
        
        # Eliminar el .md
        try:
            if md_file.exists():
                md_file.unlink()
        except Exception as e:
            pass
            
        # Mover el PDF
        shutil.move(str(pdf_file), str(destino_pdf))
        
    print("Limpieza completada exitosamente.")
