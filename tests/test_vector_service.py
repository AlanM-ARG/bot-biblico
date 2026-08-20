import pytest
import tempfile
import os
from services.vector_service import VectorService
from models.resource import Resource

@pytest.fixture(scope="module")
def vector_service():
    # Use ephemeral client for fast, isolated tests
    return VectorService(use_ephemeral=True)

def test_strip_frontmatter(vector_service):
    content = "---\ntest: true\n---\nHello World"
    clean = vector_service._strip_frontmatter(content)
    assert clean == "Hello World"
    
    no_frontmatter = "Hello World Only"
    assert vector_service._strip_frontmatter(no_frontmatter) == "Hello World Only"

def test_chunk_text(vector_service):
    text = "Paragraph 1.\n\nParagraph 2 is a bit longer.\n\nParagraph 3."
    
    # Test with very small max size to force splitting every paragraph
    chunks = vector_service.chunk_text(text, max_chunk_size=10)
    assert len(chunks) == 3
    assert chunks[0]["text"] == "Paragraph 1."
    
    # Test with large max size to combine paragraphs
    combined_chunks = vector_service.chunk_text(text, max_chunk_size=1000)
    assert len(combined_chunks) == 1
    assert "Paragraph 1." in combined_chunks[0]["text"]
    assert "Paragraph 3." in combined_chunks[0]["text"]
    
    # Test semantic splitting with headers
    header_text = "# Soteriología\n\nTexto sobre salvación.\n\n## Justificación\n\nTexto sobre justificación."
    header_chunks = vector_service.chunk_text(header_text, max_chunk_size=5000)
    assert len(header_chunks) >= 2
    assert header_chunks[0]["headers"]["Tema_Principal"] == "Soteriología"
    assert header_chunks[1]["headers"]["Seccion"] == "Justificación"

def test_vectorize_resource_logic(vector_service):
    # This test verifies the end-to-end logic of chunking -> embedding -> chromadb
    # We use a mocked resource id since we aren't testing SQLite here
    content = "---\ncat: test\n---\nSentence one.\n\nSentence two."
    
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        mock_resource = Resource(
            id=999,
            filename="test.md",
            filepath=tmp_path,
            resource_type="documento",
            category="general",
            md5_hash="fakehash",
            metadata_json="{}"
        )
        
        # Call vectorize (it will attempt to update DB, so we patch repo in memory)
        vector_service.repo.mark_as_vectorized = lambda x: None
        
        success = vector_service.vectorize_resource(mock_resource)
        assert success is True
        
        # Verify it went into ChromaDB
        results = vector_service.collection.get(
            where={"resource_id": 999}
        )
        assert len(results['ids']) == 1 # 1 chunk because max size combines the 2 sentences
        assert "Sentence one." in results['documents'][0]
        
    finally:
        os.unlink(tmp_path)
