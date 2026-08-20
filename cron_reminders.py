import os
import requests
import time
from dotenv import load_dotenv
from services.rag_service import RAGService
from repositories.user_repository import UserRepository
from database.connection import get_connection
from models.rag_response import RAGResponse
from services.rag_logger import RAGLogger, RAGLogEntry

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_latest_study_topic(user_id: int) -> str:
    """Retrieves the latest topic or chapter the user has been studying."""
    from database.connection import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check user_roadmaps logs first as an indicator of recent study topics
    cursor.execute("""
        SELECT topic FROM user_roadmaps 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['topic']:
        snippet = row['topic'][:100]
        return f"el plan de estudio sobre: '{snippet}'"
        
    return "La Soberanía de Dios"

def trigger_discord_reminder():
    """Generates a grace reminder for all users and sends it to Discord."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No DISCORD_WEBHOOK_URL found in .env. Skipping reminder.")
        return False

    print("Iniciando Bot de Recordatorios de Gracia...")
    user_repo = UserRepository()
    rag_service = RAGService()
    
    users = user_repo.get_all_users()
    
    for user in users:
        topic = get_latest_study_topic(user.id)
        print(f"Generando recordatorio para {user.username} sobre '{topic}'...")
        
        # Inject context if available
        context_str = f" Contexto Vital del usuario: {user.vital_context}." if user.vital_context else ""
        
        prompt = f"""Actúa como un pastor reformado enviando un mensaje directo y muy breve por Discord a un miembro de su iglesia que está terminando su jornada secular.
El tema de estudio reciente del usuario fue: "{topic}".{context_str}

OBJETIVO:
Escribe un "Recordatorio de Gracia" (máximo 50-60 palabras).
1. Saca al usuario del piloto automático secular.
2. Recuérdale proactivamente al menos una de estas disciplinas espirituales para hoy: la oración secreta, la adoración familiar, o el estudio bíblico extenso de la Palabra.
3. Cruza sutilmente el tema de estudio reciente con su necesidad de aplicar la gracia hoy.
Usa tono animante, directo, y formato Markdown de Discord (usa negritas **texto** y algún emoji pastoral o de tecnología 💻). No uses saludos formales largos.

EJEMPLO (No copies):
"💻 **¡Pausa de 1 minuto!** Hoy estudiaste Romanos 8. No importa si tu código falla hoy, tu justificación en Cristo no falla. Descansá en Su gracia y seguí trabajando con gozo. ☕"

FORMATO DE SALIDA ESTRUCTURADA (obligatorio):
Responde SIEMPRE como un JSON válido con esta forma exacta:
{{
  "content": "<tu recordatorio aquí en markdown>",
  "sources_used": ["<tema estudiado>"],
  "fallback_no_rag": false,
  "recommended_resources": []
}}
"""
        
        try:
            start_time = time.time()
            log_entry = RAGLogEntry(module="cron_discord_reminder", query=topic)
            
            raw_response = rag_service._call_llm(prompt, module="cron_discord_reminder")
            log_entry.model_used = rag_service._last_model_used
            
            response_obj = RAGResponse.parse(raw_response, query_topic=topic)
            reminder_text = response_obj.content
            
            log_entry.duration_ms = int((time.time() - start_time) * 1000)
            logger = RAGLogger()
            logger.log(log_entry)
            
            # Send to Discord
            payload = {
                "content": f"🔔 Recordatorio para **{user.display_name or user.username}**:\n\n{reminder_text}"
            }
            
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code in [200, 204]:
                print(f"✅ Recordatorio enviado exitosamente a {user.username}.")
            else:
                print(f"❌ Error al enviar a Discord: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Error generando recordatorio para {user.username}: {str(e)}")
            
    return True

if __name__ == "__main__":
    trigger_discord_reminder()
