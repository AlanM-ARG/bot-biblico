import json
import os
import re

class BibleParserService:
    def __init__(self, raw_dir="data_raw/Versiones biblia", output_dir="data/processed/bibles"):
        self.raw_dir = raw_dir
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _sanitize_filename(self, text):
        return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '_')

    def parse_version(self, file_name: str):
        """
        Parses a JSON bible version and splits it into chapter-level Markdown files 
        optimized for RAG token consumption.
        """
        file_path = os.path.join(self.raw_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Bible file not found: {file_path}")
            
        print(f"Parsing Bible Version: {file_name}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        version_abbr = data.get("local_abbreviation", os.path.splitext(file_name)[0])
        
        count = 0
        for book in data.get("books", []):
            book_name = book.get("name", "Unknown_Book")
            safe_book_name = self._sanitize_filename(book_name)
            
            for chapter in book.get("chapters", []):
                chapter_obj = chapter.get("current", {})
                if isinstance(chapter_obj, dict):
                    chapter_num_raw = chapter_obj.get("human", "1").split()[-1]
                else:
                    chapter_num_raw = str(chapter_obj)
                    
                chapter_num = self._sanitize_filename(chapter_num_raw)
                
                # Build the markdown content
                md_content = f"---\n"
                md_content += f"category: \"biblia\"\n"
                md_content += f"resource_type: \"capitulo_biblico\"\n"
                md_content += f"version: \"{version_abbr}\"\n"
                md_content += f"libro: \"{book_name}\"\n"
                md_content += f"capitulo: {chapter_num}\n"
                md_content += f"---\n\n"
                
                md_content += f"# {book_name} {chapter_num} ({version_abbr})\n\n"
                
                # Extract text
                for item in chapter.get("items", []):
                    item_type = item.get("type", "")
                    verses = item.get("verse_numbers", [])
                    lines = item.get("lines", [])
                    text = " ".join(lines)
                    
                    if "heading" in item_type:
                        md_content += f"### {text}\n\n"
                    else:
                        if verses:
                            # Use the first verse number in the array for marking
                            v_num = verses[0]
                            md_content += f"**{v_num}** {text} "
                        else:
                            md_content += f"{text} "
                
                # Save the chapter file
                output_filename = f"{version_abbr}_{safe_book_name}_{chapter_num}.md"
                output_path = os.path.join(self.output_dir, output_filename)
                
                with open(output_path, "w", encoding="utf-8") as out_f:
                    out_f.write(md_content)
                
                count += 1
                
        print(f"Successfully chunked {count} chapters for {version_abbr}.")
        return count
