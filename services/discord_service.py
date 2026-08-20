import os
import requests
import json
from typing import Optional

class DiscordService:
    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    def send_message(self, content: str) -> bool:
        """
        Envía un mensaje al Webhook de Discord configurado.
        Retorna True si fue exitoso, False en caso contrario.
        """
        if not self.webhook_url:
            print("[DiscordService] Error: DISCORD_WEBHOOK_URL no configurado.")
            return False

        payload = {
            "content": content
        }

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"[DiscordService] Error al enviar notificación: {e}")
            return False
