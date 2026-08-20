import pytest
from unittest.mock import patch, MagicMock
from services.cross_reference_service import CrossReferenceService
from models.resource import Resource

@pytest.fixture(scope="module")
def cross_ref_service():
    return CrossReferenceService(use_ephemeral_db=True)

@patch('repositories.resource_repository.ResourceRepository.get_all')
def test_get_related_resources(mock_get_all, cross_ref_service):
    # Mocking SQLite Repo
    res1 = Resource(id=10, filename="sermon.md", filepath="sermon.md", resource_type="audio_transcrito", category="predicacion_local", md5_hash="1", metadata_json='{}')
    res2 = Resource(id=20, filename="credo.md", filepath="credo.md", resource_type="documento", category="credo", md5_hash="2", metadata_json='{}')
    
    mock_get_all.return_value = [res1, res2]
    
    # Manually inject data into the ephemeral ChromaDB collection for testing
    cross_ref_service.collection.add(
        documents=["La gracia es un don inmerecido de Dios.", "Este es un credo sobre la gracia divina.", "Lente hermeneutico base no mostrar."],
        embeddings=[[0.1]*384, [0.12]*384, [0.15]*384], # Dummy embeddings matching 'all-MiniLM-L6-v2' size
        metadatas=[{"resource_id": 10, "category": "predicacion_local"}, {"resource_id": 20, "category": "credo"}, {"resource_id": 99, "category": "doctrina_local"}],
        ids=["chunk1", "chunk2", "chunk3"]
    )
    
    # Query something related to Grace
    # Since embeddings are dummy, it will just retrieve everything, but our logic filters it
    related = cross_ref_service.get_related_resources("gracia", limit=5)
    
    # We should get exactly 2 back (the sermon and the creed), the doctrine anchor is filtered
    assert len(related) == 2
    
    categories = [r.category for r in related]
    assert "doctrina_local" not in categories
    assert "predicacion_local" in categories
    assert "credo" in categories
