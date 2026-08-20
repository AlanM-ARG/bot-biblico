import os
import pytest
import tempfile
from services.resource_service import ResourceService

@pytest.fixture
def resource_service():
    return ResourceService()

def test_calculate_md5(resource_service):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"hello world")
        tmp_path = tmp.name
        
    try:
        # MD5 of "hello world" is 5eb63bbbe01eeed093cb22bb8f5acdc3
        md5 = resource_service.calculate_md5(tmp_path)
        assert md5 == "5eb63bbbe01eeed093cb22bb8f5acdc3"
    finally:
        os.unlink(tmp_path)

def test_parse_frontmatter(resource_service):
    content = """---
category: "teologia"
resource_type: "articulo"
autor: "Spurgeon"
---

# Título
Contenido...
"""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        metadata = resource_service.parse_frontmatter(tmp_path)
        assert metadata["category"] == "teologia"
        assert metadata["resource_type"] == "articulo"
        assert metadata["autor"] == "Spurgeon"
    finally:
        os.unlink(tmp_path)

def test_parse_frontmatter_no_frontmatter(resource_service):
    content = "# Just a header\nNo frontmatter here."
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        metadata = resource_service.parse_frontmatter(tmp_path)
        assert metadata["category"] == "general" # Default
        assert metadata["resource_type"] == "documento" # Default
    finally:
        os.unlink(tmp_path)

def test_ingest_file_anti_duplicate(resource_service):
    # This test relies on conftest.py clearing the DB and patching it
    content = """---
category: "test_cat"
---
# Test Document
"""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".md") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        # First ingest
        res1 = resource_service.ingest_file(tmp_path)
        assert res1 is not None
        assert res1.id is not None
        assert res1.category == "test_cat"
        
        # Second ingest (should return existing, not create new)
        res2 = resource_service.ingest_file(tmp_path)
        assert res2.id == res1.id
        
    finally:
        os.unlink(tmp_path)
