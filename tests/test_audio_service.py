import pytest
import os
from unittest.mock import patch, MagicMock
from services.audio_service import AudioService

@pytest.fixture
def audio_service():
    # We mock the WhisperModel initialization to prevent downloading models during tests
    with patch('services.audio_service.WhisperModel') as MockModel:
        service = AudioService()
        service.model = MockModel.return_value
        yield service

def test_transcribe_file_not_found(audio_service):
    with pytest.raises(FileNotFoundError):
        audio_service.transcribe("non_existent_file.mp3")

def test_transcribe_success(audio_service, tmp_path):
    # Setup mock file
    mock_file = tmp_path / "test.mp3"
    mock_file.write_text("dummy content")
    
    # Setup mock return values for segments
    mock_segment1 = MagicMock()
    mock_segment1.text = "Hola"
    mock_segment2 = MagicMock()
    mock_segment2.text = "Mundo"
    
    audio_service.model.transcribe.return_value = ([mock_segment1, mock_segment2], {"language": "es"})
    
    result = audio_service.transcribe(str(mock_file))
    assert result == "Hola Mundo"
