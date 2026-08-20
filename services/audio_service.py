import os
from faster_whisper import WhisperModel

class AudioService:
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        """
        Initializes the Whisper model. 
        Using faster-whisper with base model and int8 compute type makes it 
        extremely fast and memory efficient for local CPU usage.
        """
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        
    def transcribe(self, file_path: str) -> str:
        """
        Transcribes an audio file into text.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        segments, info = self.model.transcribe(file_path, beam_size=5)
        
        # Combine segments into a single string
        text = ""
        for segment in segments:
            text += segment.text + " "
            
        return text.strip()
