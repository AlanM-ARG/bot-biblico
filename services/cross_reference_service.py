import os
from repositories.resource_repository import ResourceRepository
from core.embeddings import get_encoder
from core.vector_db import get_collection

class CrossReferenceService:
    def __init__(self, use_ephemeral_db=False):
        self.repo = ResourceRepository()
        self.encoder = get_encoder()
        
        if use_ephemeral_db:
            import chromadb
            self.db_client = chromadb.EphemeralClient()
            self.collection = self.db_client.get_or_create_collection(name="biblico_collection")
        else:
            self.collection = get_collection()

    def get_related_resources(self, query: str, limit: int = 3) -> list:
        """
        Busca recursos relacionados al tema consultado en la base de datos vectorial,
        excluyendo el lente hermenéutico base, y agrupándolos por recurso para no
        devolver chunks duplicados del mismo archivo.
        """
        query_embedding = self.encoder.encode([query]).tolist()
        
        # We query more results than the limit because we will filter out duplicates 
        # and base doctrine chunks.
        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=15
            )
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return []

        if not results['metadatas'] or not results['metadatas'][0]:
            return []

        recommended_resources = []
        seen_resource_ids = set()

        for meta in results['metadatas'][0]:
            if not meta:
                continue
                
            res_id = meta.get("resource_id")
            category = meta.get("category")
            
            # Exclude the doctrinal anchor, we only want to recommend 
            # supplementary materials like creeds, sermons, or reading plans
            if category == "doctrina_local":
                continue
                
            if res_id and res_id not in seen_resource_ids:
                # Fetch full resource details from SQLite
                # Since we don't have a direct get_by_id in ResourceRepository yet,
                # we'll fetch it by doing a quick loop or we could add get_by_id to repo.
                # Let's just use the metadata to build a generic dict for the MVP UI
                # if we don't want to alter the repo again.
                seen_resource_ids.add(res_id)
                
                # Fetch all resources to find by ID (not optimal for scale, but works for MVP)
                # Ideally, add get_by_id to repo. Let's just do it directly.
                all_resources = self.repo.get_all()
                res_obj = next((r for r in all_resources if r.id == res_id), None)
                
                if res_obj:
                    recommended_resources.append(res_obj)
                    
                if len(recommended_resources) >= limit:
                    break
                    
        return recommended_resources

    def get_exact_references(self, book: str, chapter: int, limit: int = 5) -> list:
        """
        Realiza una búsqueda exacta usando la tabla de referencias cruzadas de OpenBible (SQLite).
        """
        # Map Spanish book names to OpenBible abbreviations (minimal example, to be expanded)
        book_map = {
            "génesis": "Gen", "éxodo": "Exod", "levítico": "Lev", "números": "Num", "deuteronomio": "Deut",
            "mateo": "Matt", "marcos": "Mark", "lucas": "Luke", "juan": "John",
            "romanos": "Rom", "1 corintios": "1Cor", "2 corintios": "2Cor",
            "gálatas": "Gal", "efesios": "Eph", "filipenses": "Phil", "colosenses": "Col",
            "1 tesalonicenses": "1Thess", "2 tesalonicenses": "2Thess",
            "1 timoteo": "1Tim", "2 timoteo": "2Tim", "tito": "Titus", "filemón": "Phlm",
            "hebreos": "Heb", "santiago": "Jas", "1 pedro": "1Pet", "2 pedro": "2Pet",
            "1 juan": "1John", "2 juan": "2John", "3 juan": "3John", "judas": "Jude",
            "apocalipsis": "Rev"
        }
        
        abbrev = book_map.get(book.lower().strip(), book[:3].capitalize())
        prefix = f"{abbrev}.{chapter}.%"
        
        from database.connection import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT target_verse, sum(votes) as total_votes 
            FROM cross_references 
            WHERE source_verse LIKE ? 
            GROUP BY target_verse
            ORDER BY total_votes DESC 
            LIMIT ?
        ''', (prefix, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        class MockResource:
            def __init__(self, target_verse, total_votes):
                self.id = f"openbible_{target_verse}"
                self.filename = f"Referencia: {target_verse} (OpenBible)"
                self.category = "cross_reference"
                self.resource_type = "openbible"
                self.metadata_json = "{}"
                
        exact_resources = []
        if rows:
            for row in rows:
                exact_resources.append(MockResource(row['target_verse'], row['total_votes']))
        
        # We can also append the exact matches from ChromaDB as fallback/complement
        try:
            results = self.collection.get(
                where={
                    "$and": [
                        {"book": book},
                        {"chapter": chapter}
                    ]
                },
                limit=limit
            )
            if results['metadatas']:
                seen_resource_ids = set()
                for meta in results['metadatas']:
                    res_id = meta.get("resource_id")
                    if res_id and res_id not in seen_resource_ids:
                        seen_resource_ids.add(res_id)
                        all_resources = self.repo.get_all()
                        res_obj = next((r for r in all_resources if r.id == res_id), None)
                        if res_obj:
                            exact_resources.append(res_obj)
        except Exception as e:
            print(f"Error querying exact references ChromaDB: {e}")

        return exact_resources
