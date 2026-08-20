import os
import requests
import zipfile
from pathlib import Path

class OpenBibleService:
    def __init__(self, output_dir="data/openbible"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def download_file(self, url: str, target_filename: str) -> Path:
        """Downloads a file from a given URL."""
        print(f"Downloading {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        target_path = self.output_dir / target_filename
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Downloaded successfully to {target_path}")
        return target_path
        
    def extract_zip(self, zip_path: Path, extract_to: Path = None) -> Path:
        """Extracts a ZIP file."""
        if extract_to is None:
            extract_to = self.output_dir / zip_path.stem
            
        extract_to.mkdir(parents=True, exist_ok=True)
        
        print(f"Extracting {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
            
        return extract_to

    def sync_topics(self):
        """Downloads the topics raw counts and converts them to optimized markdown."""
        url = "https://a.openbible.info/data/topic-votes.txt"
        file_path = self.download_file(url, "topic-votes.txt")
        
        print("Parsing topics into Markdown...")
        topics_dir = self.output_dir / "topics_md"
        topics_dir.mkdir(exist_ok=True)
        
        # topic-votes.txt format: topic <tab> verse <tab> votes
        # Group by topic, keep verses with > 0 votes.
        from collections import defaultdict
        topic_map = defaultdict(list)
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 3 and parts[0] != "Topic":
                    topic, verse = parts[0], parts[1]
                    try:
                        votes = int(parts[2]) if parts[2] else 0
                    except ValueError:
                        votes = 0
                        
                    if votes > 0:
                        topic_map[topic].append((verse, votes))
                        
        # Create a single markdown file per topic (max top 50 verses per topic to save tokens)
        count = 0
        for topic, verses in topic_map.items():
            safe_topic = "".join(c for c in topic if c.isalnum() or c in " -_").replace(" ", "_")
            md_path = topics_dir / f"Tema_{safe_topic}.md"
            
            # Sort by votes descending and keep top 20
            verses.sort(key=lambda x: x[1], reverse=True)
            top_verses = verses[:20]
            
            with open(md_path, "w", encoding="utf-8") as out:
                out.write("---\n")
                out.write("category: \"openbible_topic\"\n")
                out.write("resource_type: \"mapa_tematico\"\n")
                out.write(f"tema: \"{topic}\"\n")
                out.write("---\n\n")
                out.write(f"# Referencias Bíblicas sobre: {topic}\n\n")
                for v, votes in top_verses:
                    out.write(f"- {v} ({votes} votos)\n")
            count += 1
            
        print(f"Created {count} topic map markdown files.")

    def sync_cross_references(self):
        """Downloads and extracts cross references."""
        url = "https://a.openbible.info/data/cross-references.zip"
        zip_path = self.download_file(url, "cross-references.zip")
        extract_dir = self.extract_zip(zip_path)
        print("Cross-references synced. (Will be parsed into MD similarly in next iteration).")
        
    def sync_geocoding(self):
        """Clones the geocoding data repo."""
        # For MVP we can just download the ZIP of the repo instead of full git clone
        url = "https://github.com/openbibleinfo/Bible-Geocoding-Data/archive/refs/heads/master.zip"
        zip_path = self.download_file(url, "Bible-Geocoding-Data.zip")
        self.extract_zip(zip_path, self.output_dir / "geocoding_data")
        
        # Download thumbnails
        thumb_url = "https://a.openbible.info/geo/thumbnails.zip"
        thumb_zip = self.download_file(thumb_url, "thumbnails.zip")
        self.extract_zip(thumb_zip, self.output_dir / "thumbnails")
        print("Geocoding data synced.")
