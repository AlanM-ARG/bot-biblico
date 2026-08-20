import pytest
from services.prompt_builder import PromptBuilder
from models.user import User

def test_prompt_builder_injects_nbei_principiante():
    pb = PromptBuilder()
    user = User(id=1, username="test", study_level="principiante")
    
    prompt = pb.build_system_prompt(user, "Romanos 8", ["Contexto"])
    
    assert "Paso 2: Las seis preguntas básicas" in prompt
    assert "Paso 9: Descubrir una lección para la vida" in prompt
    assert "Enseñanza: ¿qué dice la Palabra?" not in prompt

def test_prompt_builder_injects_nbei_complejo():
    pb = PromptBuilder()
    user = User(id=1, username="test", study_level="complejo")
    
    prompt = pb.build_system_prompt(user, "Romanos 8", ["Contexto"])
    
    assert "OBSERVACIÓN (los 10 pasos completos):" in prompt
    assert "INTERPRETACIÓN (las 6 pautas completas):" in prompt
    assert "APLICACIÓN (los 4 ejes según 2 Timoteo 3:16-17):" in prompt

def test_prompt_builder_enforces_json_output():
    pb = PromptBuilder()
    user = User(id=1, username="test")
    
    prompt = pb.build_system_prompt(user, "Romanos 8", ["Contexto"])
    
    assert "FORMATO DE SALIDA ESTRUCTURADA (obligatorio)" in prompt
    assert '"content":' in prompt
    assert '"fallback_no_rag":' in prompt
    assert "REGLA DE CONTEXTO INSUFICIENTE (fallback educativo con transparencia total" in prompt

def test_prompt_builder_audience_logic():
    pb = PromptBuilder()
    # User with vital context and family mode off
    user1 = User(id=1, username="test1", vital_context="Trabajo remoto", family_mode=False)
    prompt1 = pb.build_system_prompt(user1, "Romanos 8", ["Contexto"])
    assert "Trabajo remoto" in prompt1
    
    # User with vital context and family mode on (no audience provided)
    user2 = User(id=2, username="test2", vital_context="Trabajo remoto", family_mode=True)
    prompt2 = pb.build_system_prompt(user2, "Romanos 8", ["Contexto"])
    assert "Trabajo remoto" not in prompt2
    assert "lenguaje simple y neutro por defecto" in prompt2
    
    # User with vital context and family mode on AND audience provided
    prompt3 = pb.build_system_prompt(user2, "Romanos 8", ["Contexto"], audiencia={"relacion": "hijo", "edad": 6})
    assert "Trabajo remoto" not in prompt3
    assert "relacion: hijo, edad: 6" in prompt3
