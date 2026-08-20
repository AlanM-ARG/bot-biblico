from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class RAGResponse:
    """
    Typed model for the structured JSON output from the LLM.
    Matches the FORMATO DE SALIDA ESTRUCTURADA defined in contexto_aplicativo_biblico.md (section 8).
    """
    content: str = ""
    sources_used: list = field(default_factory=list)
    fallback_no_rag: bool = False
    recommended_resources: list = field(default_factory=list)
    missing_topics: list = field(default_factory=list)

    @staticmethod
    def parse(raw_text: str, query_topic: str = None) -> 'RAGResponse':
        """
        Defensive parser: tries to extract a RAGResponse from LLM output.
        
        Handles:
        1. Clean JSON string
        2. JSON wrapped in ```json ... ``` markdown blocks
        3. Plain text fallback (wraps text as content, marks parse failure)
        """
        if not raw_text or not raw_text.strip():
            return RAGResponse(content="No se recibió respuesta del modelo.")

        text = raw_text.strip()

        # Attempt 1: Direct JSON parse
        try:
            data = json.loads(text)
            return RAGResponse._from_dict(data, query_topic)
        except (json.JSONDecodeError, ValueError):
            pass

        # Attempt 2: Extract from ```json ... ``` block
        if "```json" in text:
            try:
                start = text.index("```json") + len("```json")
                end = text.index("```", start)
                json_str = text[start:end].strip()
                data = json.loads(json_str)
                return RAGResponse._from_dict(data, query_topic)
            except (ValueError, json.JSONDecodeError):
                pass
        # Attempt 3: Extract from ``` ... ``` block (without json tag)
        if "```" in text:
            try:
                start = text.index("```") + len("```")
                end = text.index("```", start)
                json_str = text[start:end].strip()
                data = json.loads(json_str)
                return RAGResponse._from_dict(data, query_topic)
            except (ValueError, json.JSONDecodeError):
                pass

        # Attempt 4: Find first { and last } and try to parse
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                json_str = text[first_brace:last_brace + 1]
                data = json.loads(json_str)
                return RAGResponse._from_dict(data, query_topic)
            except (json.JSONDecodeError, ValueError):
                pass
                
        # Attempt 5: Regex extraction for malformed JSON with literal newlines
        import re
        content_match = re.search(r'"content"\s*:\s*"(.*)"\s*,\s*"sources_used"', text, re.DOTALL)
        if content_match:
            try:
                extracted_content = content_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                
                fallback = False
                if re.search(r'"fallback_no_rag"\s*:\s*true', text, re.IGNORECASE):
                    fallback = True
                    
                sources = []
                sources_match = re.search(r'"sources_used"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if sources_match:
                    sources = re.findall(r'"([^"]*)"', sources_match.group(1))
                    
                rec_resources = []
                rec_match = re.search(r'"recommended_resources"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if rec_match:
                    rec_resources = re.findall(r'"([^"]*)"', rec_match.group(1))
                    
                return RAGResponse._from_dict({
                    "content": extracted_content,
                    "sources_used": sources,
                    "fallback_no_rag": fallback,
                    "recommended_resources": rec_resources
                }, query_topic)
            except Exception:
                pass

        # Attempt 4: Find first { and last } and try to parse
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                json_str = text[first_brace:last_brace + 1]
                data = json.loads(json_str)
                return RAGResponse._from_dict(data, query_topic)
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: treat entire text as content (the LLM didn't follow JSON format)
        return RAGResponse(
            content=text,
            sources_used=[],
            fallback_no_rag=False,
            recommended_resources=[]
        )

    @staticmethod
    def _from_dict(data: dict, query_topic: str = None) -> 'RAGResponse':
        """Safely construct a RAGResponse from a dict, tolerating missing keys and applying validation."""
        content = data.get("content", "")
        sources_used = data.get("sources_used", [])
        fallback_no_rag = data.get("fallback_no_rag", False)
        recommended_resources = data.get("recommended_resources", [])
        missing_topics = data.get("missing_topics", [])
        
        # Defensive validation of sources_used
        if not sources_used:
            fallback_no_rag = True
        elif query_topic:
            # If the only source is exactly the passage name or topic
            if len(sources_used) == 1 and sources_used[0].strip().lower() == query_topic.strip().lower():
                fallback_no_rag = True
                
        return RAGResponse(
            content=content,
            sources_used=sources_used,
            fallback_no_rag=fallback_no_rag,
            recommended_resources=recommended_resources,
            missing_topics=missing_topics
        )
