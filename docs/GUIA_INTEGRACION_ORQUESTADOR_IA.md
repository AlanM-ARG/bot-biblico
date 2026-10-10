# 🤖 Guía de Integración: Orquestador de API Keys de IA

> **Audiencia**: Desarrolladores de bots que quieran conectarse al sistema compartido de enrutamiento de LLMs del ecosistema Bot Bíblico.
>
> **Última actualización**: Septiembre 2026

---

## 📋 Índice

1. [Arquitectura General](#1-arquitectura-general)
2. [Opción A: Usar LiteLLM Proxy (Recomendada)](#2-opción-a-usar-litellm-proxy-recomendada)
3. [Opción B: Integrar TierRouter como Librería Python](#3-opción-b-integrar-tierrouter-como-librería-python)
4. [Configuración de API Keys (.env)](#4-configuración-de-api-keys-env)
5. [Catálogo de Modelos y Tiers](#5-catálogo-de-modelos-y-tiers)
6. [Ollama como Fallback Local](#6-ollama-como-fallback-local)
7. [Observabilidad con Langfuse](#7-observabilidad-con-langfuse)
8. [Ejemplos Prácticos de Integración](#8-ejemplos-prácticos-de-integración)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Arquitectura General

```
┌───────────────────────────────────────────────────────────────────┐
│                    BOTS / APLICACIONES                            │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│  │ Bot Bíbl │  │ Bot Discord  │  │ Otro Bot (tu proyecto)     │  │
│  └────┬─────┘  └──────┬───────┘  └────────────┬───────────────┘  │
│       │               │                        │                  │
│  ┌────▼───────────────▼────────────────────────▼───────────────┐  │
│  │          LiteLLM Proxy  (localhost:4000/v1)                 │  │
│  │    Endpoint unificado OpenAI-compatible para TODOS          │  │
│  └────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┘  │
│       │       │       │       │       │       │       │           │
│  ┌────▼──┐┌───▼──┐┌───▼──┐┌──▼───┐┌──▼───┐┌──▼────┐┌─▼──────┐  │
│  │Gemini ││Groq  ││Mistr ││OpenR ││Z.AI  ││DeepS  ││Ollama  │  │
│  │3.5-3.8││GPT120││al    ││outer ││      ││eek    ││Local   │  │
│  └───────┘└──────┘└──────┘└──────┘└──────┘└───────┘└────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │       Langfuse (localhost:3000) — Observabilidad          │    │
│  │       Tracing, métricas, costos por modelo y bot          │    │
│  └───────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

### Flujo de Fallback (Cascada Automática)

```
Tier 1 (Contexto Grande)     → Gemini 3.7-flash → 3.6-flash → 3.8-flash → 3.1-pro-preview
         ↓ si falla todo
Tier 2 (Disponibilidad)      → Gemini 3.5-flash → flash-latest → Groq GPT-120b → Groq Qwen-27b → Mistral → OpenRouter → Z.AI
         ↓ si falla todo
Tier 3 (Tareas Cortas)       → Gemini 3.5-flash-lite → 3.1-flash-lite → flash-lite-latest → Cerebras
         ↓ si falla todo
Escalón Casi-Gratis           → DeepSeek Chat
         ↓ si falla todo
Tier 4 (Local / Offline)     → Ollama (llama3.1 local)
```

---

## 2. Opción A: Usar LiteLLM Proxy (Recomendada)

> **Esta es la forma más simple.** Tu bot solo necesita hablar con un endpoint OpenAI-compatible en `localhost:4000/v1`.

### 2.1. Pre-requisitos

- LiteLLM Proxy debe estar corriendo (el script `start_full_stack.ps1` lo levanta automáticamente)
- Si solo necesitas el proxy: `litellm --config litellm_config.yaml --port 4000`

### 2.2. Conexión desde Python (OpenAI SDK)

```python
from openai import OpenAI

# Conectar al proxy local — NO necesitas API keys individuales
client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-litellm-master-key"  # Master key del proxy
)

# Usar cualquier modelo registrado en litellm_config.yaml
response = client.chat.completions.create(
    model="gemini-pro",           # Alias que apunta a gemini-3.7-flash
    # model="gemini-flash",       # Alias → gemini-3.6-flash
    # model="tier1-largo",        # Alias → gemini-3.7-flash
    # model="tier2-rapido",       # Alias → gemini-3.5-flash
    # model="tier3-corto",        # Alias → gemini-3.5-flash-lite
    # model="ollama-local",       # Forzar modelo local
    messages=[
        {"role": "system", "content": "Eres un asistente bíblico."},
        {"role": "user", "content": "Explica Juan 3:16"}
    ],
    temperature=0.3,
)

print(response.choices[0].message.content)
```

### 2.3. Conexión desde Node.js / TypeScript

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:4000/v1',
  apiKey: 'sk-litellm-master-key',
});

const response = await client.chat.completions.create({
  model: 'gemini-pro',  // o cualquier modelo/alias del catálogo
  messages: [
    { role: 'system', content: 'Eres un asistente bíblico.' },
    { role: 'user', content: 'Explica Juan 3:16' }
  ],
  temperature: 0.3,
});

console.log(response.choices[0].message.content);
```

### 2.4. Conexión desde cURL / cualquier lenguaje

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-litellm-master-key" \
  -d '{
    "model": "gemini-pro",
    "messages": [
      {"role": "system", "content": "Eres un asistente bíblico."},
      {"role": "user", "content": "Explica Juan 3:16"}
    ],
    "temperature": 0.3
  }'
```

### 2.5. Fallbacks Automáticos del Proxy

El proxy tiene fallbacks configurados automáticamente en `litellm_config.yaml`:

| Modelo solicitado | Fallback en orden |
|---|---|
| `gemini-pro` | `gemini-3.5-flash` → `gemini-3.1-pro-preview` → `groq-gpt-120b` → `groq-qwen-27b` → `ollama-local` |
| `gemini-flash` | `gemini-3.5-flash` → `groq-gpt-120b` → `ollama-local` |
| `tier1-largo` | `gemini-3.5-flash` → `gemini-3.1-pro-preview` → `groq-gpt-120b` → `ollama-local` |

---

## 3. Opción B: Integrar TierRouter como Librería Python

> **Para bots Python que necesiten control total** sobre la lógica de enrutamiento, privacidad y estimación de tokens.

### 3.1. Instalación de Dependencias

```bash
pip install google-genai openai pyyaml python-dotenv httpx requests
```

### 3.2. Copiar los Archivos Necesarios

Tu bot necesita estos archivos del proyecto Bot Bíblico:

```
tu-bot/
├── .env                        # Copia o enlaza simbólicamente
├── data/
│   └── models_config.yaml      # Configuración de tiers y modelos
└── llm/
    ├── __init__.py              # Archivo vacío
    ├── llm_client.py            # Cliente unificado de LLMs
    └── tier_router.py           # Enrutador por tiers con fallback
```

**Archivos fuente:**
- `llm/llm_client.py` — Cliente que sabe hablar con Gemini, OpenAI-compatible y Eden AI
- `llm/tier_router.py` — Orquestador que selecciona proveedor según tier, privacidad y tamaño de prompt
- `data/models_config.yaml` — Catálogo de modelos con tiers y context windows

### 3.3. Uso Básico

```python
from llm.tier_router import TierRouter

router = TierRouter(config_path="data/models_config.yaml")

# El router elige automáticamente el mejor proveedor según el módulo
result = router.route(
    prompt="Explica la justificación por fe según Romanos 5",
    module="study_guide",           # → tier_1_contexto_grande
    system_prompt="Eres un teólogo reformado bautista.",
    temperature=0.3,
    # timeout=180,                  # Opcional, hay defaults por tier
    # contains_private_data=False,  # True excluye agregadores como OpenRouter
)

if result.success:
    print(f"✅ Respuesta de {result.provider_name}/{result.model_name}")
    print(f"   Latencia: {result.latency_ms}ms")
    print(result.content)
else:
    print(f"❌ Error: {result.error}")
```

### 3.4. Registrar tu Módulo en el Mapeo de Tiers

En `data/models_config.yaml`, sección `task_tier_map`:

```yaml
task_tier_map:
  # ... módulos existentes ...
  
  # Agregar los módulos de tu bot:
  mi_bot_chat: "tier_2_disponibilidad"          # Chat general → Tier 2
  mi_bot_analisis: "tier_1_contexto_grande"      # Análisis profundo → Tier 1
  mi_bot_clasificacion: "tier_3_tareas_cortas"   # Clasificación rápida → Tier 3
```

### 3.5. Proteger Datos Privados

Si tu módulo maneja datos sensibles del usuario, agrégalo a `private_data_modules`:

```yaml
private_data_modules:
  - "life_alert"
  - "family_devotional"
  - "mi_bot_datos_personales"   # ← Agrega tu módulo aquí
```

> Esto excluye automáticamente proveedores marcados como `is_aggregator: true` (OpenRouter, Z.AI) que podrían retransmitir datos a terceros.

---

## 4. Configuración de API Keys (.env)

El archivo `.env` centraliza todas las API keys. Tu bot debe:

1. **Compartir el mismo `.env`** del proyecto (enlace simbólico o copia)
2. **O definir estas variables de entorno** en su propio `.env`:

```env
# === REQUERIDAS (Tier 1 — Gemini es el proveedor principal) ===
GEMINI_API_KEY=tu_gemini_api_key_aquí

# === OPCIONALES (Tier 2 — Fallbacks cloud) ===
GROQ_API_KEY=tu_groq_api_key
MISTRAL_API_KEY=tu_mistral_api_key
OPENROUTER_API_KEY=tu_openrouter_api_key
ZAI_API_KEY=tu_zai_api_key

# === OPCIONALES (Tier 3 — Tareas cortas) ===
CEREBRAS_API_KEY=tu_cerebras_api_key

# === OPCIONAL (Escalón casi-gratis) ===
DEEPSEEK_API_KEY=tu_deepseek_api_key

# === OPCIONALES (Observabilidad con Langfuse) ===
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_BASE_URL="http://localhost:3000"
```

> [!IMPORTANT]
> La `GEMINI_API_KEY` es la mínima indispensable. Si solo configuras esa, el sistema usa Gemini para los tiers 1–3 y cae a Ollama local como último recurso.

### Dónde Obtener las Keys (Gratis)

| Proveedor | URL de Registro | Plan Gratuito |
|---|---|---|
| **Google AI Studio (Gemini)** | https://aistudio.google.com | ✅ Generoso (rate-limited) |
| **Groq** | https://console.groq.com | ✅ Gratis (rate-limited) |
| **Mistral** | https://console.mistral.ai | ✅ Tier gratuito |
| **OpenRouter** | https://openrouter.ai | ✅ Modelos `:free` |
| **Z.AI (GLM)** | https://open.bigmodel.cn | ✅ Créditos iniciales |
| **Cerebras** | https://cloud.cerebras.ai | ✅ Preview gratuita |
| **DeepSeek** | https://platform.deepseek.com | 💰 Muy barato ($0.14/M tokens) |
| **Ollama** | https://ollama.ai | ✅ 100% local y gratis |

---

## 5. Catálogo de Modelos y Tiers

### Modelos Disponibles vía LiteLLM Proxy

| Nombre del Modelo | Proveedor Real | Tier | Contexto Max | Notas |
|---|---|---|---|---|
| `gemini-3.8-flash` | Google AI Studio | S | 1M tokens | Más nuevo, mejor razonamiento |
| `gemini-3.7-flash` | Google AI Studio | A | 1M tokens | Muy estable, buen balance |
| `gemini-3.6-flash` | Google AI Studio | A | 1M tokens | Probado, buena fidelidad |
| `gemini-3.1-pro-preview` | Google AI Studio | S | 1M tokens | Máximo razonamiento |
| `gemini-3.5-flash` | Google AI Studio | B | 1M tokens | Rápido, bueno para chats |
| `gemini-3.5-flash-lite` | Google AI Studio | C | 1M tokens | Ultra-rápido, ETL |
| `groq-gpt-120b` | Groq | B | 131K | Rápido, bueno para conversación |
| `groq-qwen-27b` | Groq | B | 131K | Alternativa ligera |
| `gpt-4o-mini` | OpenAI | B | 128K | Requiere API key de pago |
| `ollama-local` | Ollama (local) | D | 8K | Sin internet, llama3.1 |

### Aliases de Conveniencia

| Alias | Apunta a | Uso recomendado |
|---|---|---|
| `gemini-pro` | `gemini-3.7-flash` | Tareas de razonamiento general |
| `gemini-flash` | `gemini-3.6-flash` | Chats rápidos y fluidos |
| `tier1-largo` | `gemini-3.7-flash` | Documentos largos, RAG profundo |
| `tier2-rapido` | `gemini-3.5-flash` | Respuestas rápidas |
| `tier3-corto` | `gemini-3.5-flash-lite` | Clasificación, ETL, etiquetado |

---

## 6. Ollama como Fallback Local

Ollama se usa como **último recurso** cuando todos los proveedores cloud fallan (sin internet, cuota agotada, etc.).

### 6.1. Instalación

```bash
# Windows — Descargar instalador de https://ollama.ai
# O via winget:
winget install Ollama.Ollama
```

### 6.2. Descargar el Modelo

```bash
ollama pull llama3.1
```

### 6.3. Verificar que está corriendo

```bash
# Verificar servicio
curl http://localhost:11434/api/tags

# Debería devolver la lista de modelos instalados
```

### 6.4. Cómo se Integra

- **Vía LiteLLM Proxy**: El modelo `ollama-local` está registrado en `litellm_config.yaml` (línea 84–87). LiteLLM enruta a `http://localhost:11434` automáticamente.
- **Vía TierRouter**: Está en `data/models_config.yaml` como `tier_4_local` (líneas 149–158). El router escala automáticamente a Ollama si todos los tiers anteriores fallan.
- **Timeout extendido**: Ollama tiene un timeout de **600 segundos** (10 min) porque los modelos locales pueden ser lentos según tu hardware.

### 6.5. Llamar a Ollama Directamente (sin proxy ni router)

```python
from openai import OpenAI

# Ollama expone un endpoint OpenAI-compatible nativo
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # cualquier string funciona
)

response = client.chat.completions.create(
    model="llama3.1",
    messages=[
        {"role": "user", "content": "Hola, ¿cómo estás?"}
    ]
)
print(response.choices[0].message.content)
```

---

## 7. Observabilidad con Langfuse

Todas las llamadas que pasen por LiteLLM Proxy se loguean automáticamente en **Langfuse** (`http://localhost:3000`).

### 7.1. Qué se Registra

- Modelo usado y proveedor
- Tokens de entrada/salida
- Latencia
- Costo estimado
- Errores y reintentos

### 7.2. Metadata Personalizada por Bot

Puedes enviar metadata extra para identificar tu bot en los traces:

```python
# Via LiteLLM Proxy — agregar metadata en el header
response = client.chat.completions.create(
    model="gemini-pro",
    messages=[...],
    extra_headers={
        "x-litellm-metadata": '{"bot_name": "mi-bot-discord", "module": "chat"}'
    }
)
```

---

## 8. Ejemplos Prácticos de Integración

### 8.1. Bot de Discord (Python + discord.py)

```python
import discord
from openai import OpenAI

# Conectar al orquestador
llm = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-litellm-master-key"
)

bot = discord.Client(intents=discord.Intents.default())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith("!pregunta"):
        pregunta = message.content[10:]
        
        try:
            response = llm.chat.completions.create(
                model="gemini-pro",  # Fallback automático si Gemini falla
                messages=[
                    {"role": "system", "content": "Eres un asistente bíblico."},
                    {"role": "user", "content": pregunta}
                ],
                temperature=0.3,
            )
            await message.channel.send(response.choices[0].message.content[:2000])
        except Exception as e:
            await message.channel.send(f"❌ Error al consultar IA: {e}")
```

### 8.2. Bot de Telegram (Python + python-telegram-bot)

```python
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from openai import OpenAI

llm = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-litellm-master-key"
)

async def handle_message(update, context):
    response = llm.chat.completions.create(
        model="tier2-rapido",  # Rápido para chat
        messages=[
            {"role": "system", "content": "Eres un asistente pastoral."},
            {"role": "user", "content": update.message.text}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)

app = ApplicationBuilder().token("TU_TELEGRAM_TOKEN").build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.run_polling()
```

### 8.3. Script de Procesamiento Batch

```python
from openai import OpenAI

llm = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-litellm-master-key"
)

textos = ["Génesis 1:1", "Juan 3:16", "Romanos 8:28"]

for texto in textos:
    response = llm.chat.completions.create(
        model="tier3-corto",  # Rápido y barato para ETL
        messages=[
            {"role": "user", "content": f"Clasifica este versículo por tema: {texto}"}
        ],
        temperature=0.1,
    )
    print(f"{texto} → {response.choices[0].message.content}")
```

---

## 9. Troubleshooting

### Error: "Connection refused" en localhost:4000

```bash
# Verificar si LiteLLM está corriendo
netstat -an | findstr :4000

# Reiniciar el proxy
litellm --config litellm_config.yaml --port 4000
```

### Error: "429 RESOURCE_EXHAUSTED" (cuota agotada)

El sistema maneja esto automáticamente escalando al siguiente proveedor. Si ves este error frecuentemente:

1. Verifica cuotas en https://aistudio.google.com
2. Los fallbacks a Groq/Mistral/OpenRouter se activan automáticamente
3. DeepSeek y Ollama son el último recurso

### Error: "Timeout" con Ollama

Ollama puede ser lento dependiendo de tu hardware. Asegurate de:

1. Tener el modelo descargado: `ollama list`
2. Verificar RAM disponible: llama3.1 necesita ~8GB RAM
3. El timeout está en 600s (10 min) por defecto

### El proxy no encuentra un modelo

```bash
# Listar modelos disponibles en el proxy
curl http://localhost:4000/v1/models -H "Authorization: Bearer sk-litellm-master-key"
```

### Verificar salud del sistema

```bash
# Health check del proxy
curl http://localhost:4000/health

# Health check de Ollama
curl http://localhost:11434/

# Health check de Langfuse
curl http://localhost:3000/api/public/health
```

---

## 📌 Resumen Rápido

| Quiero... | Hago... |
|---|---|
| La integración más simple | Conecto al proxy `localhost:4000/v1` con OpenAI SDK |
| Control total del routing | Uso `TierRouter` directamente en mi código Python |
| Solo usar Ollama local | `model="ollama-local"` vía proxy, o directo a `localhost:11434/v1` |
| Ver métricas y costos | Abro Langfuse en `http://localhost:3000` |
| Agregar un nuevo modelo | Lo agrego en `litellm_config.yaml` y `models_config.yaml` |
| Proteger datos privados | Agrego mi módulo a `private_data_modules` en `models_config.yaml` |

> [!TIP]
> **¿Primer setup?** Ejecuta `.\start_full_stack.ps1` en la carpeta de Bot Bíblico. Esto levanta Docker (Langfuse), LiteLLM Proxy, Ollama, y la app Streamlit. Después, conecta tu bot al proxy en `localhost:4000/v1`.
