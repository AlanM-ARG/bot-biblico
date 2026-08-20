import pytest
from unittest.mock import patch, MagicMock
from services.discord_service import DiscordService
import requests

@patch.dict('os.environ', {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test/test'})
@patch('services.discord_service.requests.post')
def test_send_message_success(mock_post):
    # Setup mock
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Execute
    service = DiscordService()
    result = service.send_message("Mensaje de prueba")

    # Assert
    assert result is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['headers'] == {"Content-Type": "application/json"}
    assert "Mensaje de prueba" in kwargs['data']

@patch.dict('os.environ', {}, clear=True)
def test_send_message_no_webhook_url():
    # Execute
    service = DiscordService()
    result = service.send_message("Mensaje")

    # Assert
    assert result is False

@patch.dict('os.environ', {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test/test'})
@patch('services.discord_service.requests.post')
def test_send_message_request_exception(mock_post):
    # Setup mock to raise an exception
    mock_post.side_effect = requests.exceptions.RequestException("API error")

    # Execute
    service = DiscordService()
    result = service.send_message("Mensaje")

    # Assert
    assert result is False
    mock_post.assert_called_once()
