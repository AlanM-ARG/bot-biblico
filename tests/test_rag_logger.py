import os
import json
import pytest
from services.rag_logger import RAGLogger, RAGLogEntry

def test_rag_logger_creates_file_and_writes_jsonl(tmp_path):
    log_file = tmp_path / "test_rag.jsonl"
    logger = RAGLogger(str(log_file))
    
    entry = RAGLogEntry(
        query="Romanos 8",
        module="study_guide",
        model_used="gemini-3.7-flash",
        fallback_no_rag=False,
        chunks_retrieved=[{"chunk_id": "1", "score": 1.2, "snippet": "texto"}]
    )
    
    logger.log(entry)
    
    assert os.path.exists(log_file)
    with open(log_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["query"] == "Romanos 8"
        assert data["module"] == "study_guide"
        assert len(data["chunks_retrieved"]) == 1

def test_rag_logger_get_recent(tmp_path):
    log_file = tmp_path / "test_rag2.jsonl"
    logger = RAGLogger(str(log_file))
    
    logger.log(RAGLogEntry(query="1"))
    logger.log(RAGLogEntry(query="2"))
    logger.log(RAGLogEntry(query="3"))
    
    recent = logger.get_recent(2)
    assert len(recent) == 2
    # most recent first
    assert recent[0]["query"] == "3"
    assert recent[1]["query"] == "2"
