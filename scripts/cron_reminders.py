import sys
import os
import time
from datetime import datetime, timezone
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.discord_service import DiscordService
from services.rag_service import RAGService
from services.rag_logger import LOG_FILE

def get_today_studied_topic() -> str:
    """Lee el log de RAG y retorna el tema estudiado hoy (si lo hubo)."""
    if not os.path.exists(LOG_FILE):
        return None

    today_str = datetime.now(timezone.utc).isoformat()[:10]
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        # Leemos las últimas líneas iterativamente (podríamos usar RAGLogger.get_recent también)
        lines = f.readlines()
        
    # Buscar de atrás para adelante
    for line in reversed(lines):
        try:
            entry = json.loads(line)
            if entry.get("timestamp", "").startswith(today_str):
                module = entry.get("module", "")
                if module in ["study_guide", "topic_study"]:
                    return entry.get("query", "")
        except json.JSONDecodeError:
            continue
            
    return None

def send_daily_reminder():
    discord_service = DiscordService()
    if not discord_service.webhook_url:
        print("[CronReminders] No hay webhook configurado. Saliendo.")
        return

    studied_topic = get_today_studied_topic()
    
    if not studied_topic:
        print("[CronReminders] No se registró estudio hoy. Enviando mensaje genérico.")
        message = "¡Bendecido día! Recuerda apartar un tiempo para meditar en la Palabra hoy. 'Lámpara es a mis pies tu palabra, y lumbrera a mi camino' (Salmos 119:105)."
        discord_service.send_message(message)
        return

    print(f"[CronReminders] Tema estudiado hoy: {studied_topic}. Generando devocional...")
    
    # Iniciar RAGService para generar el reminder
    rag_service = RAGService()
    
    # Podemos usar el ID 1 por defecto para el sistema/cron si no sabemos el ID del usuario
    user_id = 1 
    user = rag_service.user_repo.get_user_by_id(user_id)
    if not user:
        print("[CronReminders] Usuario 1 no encontrado.")
        return

    # Construir el prompt para el recordatorio
    prompt = rag_service.prompt_builder.build_system_prompt(
        user=user,
        chapter=studied_topic,
        context_docs=[],  # El RAGService en modo reminder no necesita contexto crudo, confía en el tema. Opcionalmente podríamos recuperar fragmentos.
        lens="Ninguno",
        mode="reminder"
    )
    
    try:
        # Llamamos al LLM
        raw_response = rag_service._call_llm(prompt, module="reminder", contains_private_data=False)
        from models.rag_response import RAGResponse
        response = RAGResponse.parse(raw_response, query_topic="Recordatorio")
        
        # Enviar el mensaje final
        success = discord_service.send_message(f"**📖 Recordatorio de Gracia sobre {studied_topic}:**\n\n{response.content}")
        if success:
            print("[CronReminders] Recordatorio enviado exitosamente.")
    except Exception as e:
        print(f"[CronReminders] Error generando/enviando recordatorio: {e}")

if __name__ == "__main__":
    send_daily_reminder()
