import os
import glob
import math

def split_large_markdown_files(directory="data_raw", size_limit_mb=1.0):
    size_limit_bytes = size_limit_mb * 1024 * 1024
    # Buscar en la carpeta data_raw y sus subcarpetas
    search_path = os.path.join(directory, "**", "*.md")
    
    files = glob.glob(search_path, recursive=True)
    count = 0
    
    print(f"Buscando archivos mayores a {size_limit_mb}MB para dividirlos...")
    
    for file_path in files:
        # Evitar dividir archivos que ya tienen " - Parte" en su nombre
        if " - Parte " in file_path:
            continue
            
        file_size = os.path.getsize(file_path)
        if file_size > size_limit_bytes:
            safe_name = file_path.encode('ascii', 'ignore').decode('ascii')
            print(f"Dividiendo: {safe_name} ({file_size / 1024 / 1024:.2f} MB)")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    lines = f.readlines()
                
            # Extraer frontmatter de metadatos si existe
            frontmatter = []
            content_start_idx = 0
            if lines and lines[0].startswith("---"):
                frontmatter.append(lines[0])
                for i in range(1, len(lines)):
                    frontmatter.append(lines[i])
                    if lines[i].startswith("---"):
                        content_start_idx = i + 1
                        break
            
            content_lines = lines[content_start_idx:]
            
            # Queremos que cada parte pese máximo ~0.5 MB
            num_parts = math.ceil(file_size / (0.5 * 1024 * 1024))
            lines_per_part = math.ceil(len(content_lines) / num_parts)
            
            # Escribir las nuevas partes
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            dir_name = os.path.dirname(file_path)
            
            for p in range(num_parts):
                part_lines = content_lines[p * lines_per_part : (p + 1) * lines_per_part]
                if not part_lines:
                    break
                    
                new_file_name = f"{base_name} - Parte {p+1}.md"
                new_file_path = os.path.join(dir_name, new_file_name)
                
                with open(new_file_path, "w", encoding="utf-8") as out:
                    out.writelines(frontmatter)
                    out.write("\n")
                    out.writelines(part_lines)
            
            # Eliminar archivo masivo original para que no se ingeste de nuevo
            os.remove(file_path)
            count += 1
            print(f"  -> Se generaron {num_parts} archivos más ligeros.")
            
    print(f"\nProceso finalizado. Se dividieron {count} libros masivos con éxito.")

if __name__ == "__main__":
    split_large_markdown_files()
