from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import os
from datetime import datetime, timezone


@dataclass
class ChunkInfo:
    """Represents a single chunk retrieved from the vector store."""
    chunk_id: str = ""
    score: float = 0.0
    snippet: str = ""


@dataclass
class RAGLogEntry:
    """Structured log entry for every RAG pipeline call."""
    timestamp: str = ""
    query: str = ""
    module: str = ""  # "study_guide", "topic_study", "life_alert", etc.
    chunks_retrieved: list = field(default_factory=list)  # list of ChunkInfo dicts
    model_used: str = ""  # "gemini-3.6-flash", "groq/llama-3.3-70b", etc.
    fallback_no_rag: bool = False
    error: Optional[str] = None
    duration_ms: int = 0
    # --- Tier routing observability (populated by TierRouter) ---
    tier_used: str = ""  # "tier_1_contexto_grande", "escalon_casi_gratis", etc.
    providers_attempted: list = field(default_factory=list)  # [{name, success, error, latency_ms}]
    private_data_flag: bool = False


LOG_DIR = os.path.join("data", "logs")
LOG_FILE = os.path.join(LOG_DIR, "rag_pipeline.jsonl")


class RAGLogger:
    """
    Persists structured RAG pipeline logs to a JSONL file.
    Each line is a self-contained JSON object for easy grep/parsing.
    """

    def __init__(self, log_file: str = LOG_FILE):
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log(self, entry: RAGLogEntry) -> None:
        """Append a log entry to the JSONL file."""
        if not entry.timestamp:
            entry.timestamp = datetime.now(timezone.utc).isoformat()

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except Exception as e:
            # Logging should never crash the app
            print(f"[RAGLogger] Error writing log: {e}")

    def get_recent(self, n: int = 20) -> list[dict]:
        """Read the last N log entries (most recent first)."""
        if not os.path.exists(self.log_file):
            return []

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            entries = []
            for line in lines[-n:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
            entries.reverse()
            return entries
        except Exception:
            return []
