import pytest
from models.rag_response import RAGResponse

def test_parse_clean_json():
    raw = '{"content": "Hola", "sources_used": ["ref1"], "fallback_no_rag": true, "recommended_resources": ["Comentario"]}'
    res = RAGResponse.parse(raw)
    assert res.content == "Hola"
    assert res.sources_used == ["ref1"]
    assert res.fallback_no_rag is True
    assert res.recommended_resources == ["Comentario"]

def test_parse_markdown_wrapped_json():
    raw = '''Aquí está la respuesta:
```json
{
  "content": "Texto envuelto",
  "sources_used": [],
  "fallback_no_rag": false
}
```
Espero que te sirva.
'''
    res = RAGResponse.parse(raw)
    assert res.content == "Texto envuelto"
    # Even though JSON says fallback_no_rag: false, sources_used is empty, so it should be true
    assert res.fallback_no_rag is True

def test_parse_plain_text_fallback():
    raw = "El modelo ignoró la instrucción JSON y devolvió este texto crudo."
    res = RAGResponse.parse(raw)
    assert res.content == "El modelo ignoró la instrucción JSON y devolvió este texto crudo."
    assert res.fallback_no_rag is False  # default fallback assumes no error unless stated

def test_parse_malformed_but_brace_extractable_json():
    raw = '''Un poco de basura aquí { "content": "Solo quiero esto", "fallback_no_rag": true } y más basura allá.'''
    res = RAGResponse.parse(raw)
    assert res.content == "Solo quiero esto"
    assert res.fallback_no_rag is True

def test_defensive_sources_used_validation():
    # If the only source used is exactly the query topic, it should trigger fallback
    raw = '{"content": "A", "sources_used": ["2 Tesalonicenses 1"], "fallback_no_rag": false}'
    res = RAGResponse.parse(raw, query_topic="2 Tesalonicenses 1")
    assert res.fallback_no_rag is True
    
    # If it is empty
    raw2 = '{"content": "A", "sources_used": [], "fallback_no_rag": false}'
    res2 = RAGResponse.parse(raw2)
    assert res2.fallback_no_rag is True
    
    # If it is valid
    raw3 = '{"content": "A", "sources_used": ["Comentario a Romanos", "2 Tesalonicenses 1"], "fallback_no_rag": false}'
    res3 = RAGResponse.parse(raw3, query_topic="2 Tesalonicenses 1")
    assert res3.fallback_no_rag is False

def test_parse_literal_newlines():
    # Model returns JSON with physical newlines inside strings, which invalidates strict JSON
    raw = '''{
      "content": "Línea 1
Línea 2",
      "sources_used": ["Manual"],
      "fallback_no_rag": false
    }'''
    res = RAGResponse.parse(raw)
    assert res.content == "Línea 1\nLínea 2"
    assert res.sources_used == ["Manual"]
    assert res.fallback_no_rag is False
