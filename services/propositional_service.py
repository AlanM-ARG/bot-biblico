import re
import requests
import os

# Diccionario de género literario por libro bíblico
GENRE_MAP = {
    # Epístolas paulinas
    "romanos": "epístola", "1 corintios": "epístola", "2 corintios": "epístola",
    "gálatas": "epístola", "galatas": "epístola", "efesios": "epístola",
    "filipenses": "epístola", "colosenses": "epístola",
    "1 tesalonicenses": "epístola", "2 tesalonicenses": "epístola",
    "1 timoteo": "epístola", "2 timoteo": "epístola", "tito": "epístola",
    "filemón": "epístola", "filemon": "epístola",
    # Epístolas generales
    "hebreos": "epístola", "santiago": "epístola",
    "1 pedro": "epístola", "2 pedro": "epístola",
    "1 juan": "epístola", "2 juan": "epístola", "3 juan": "epístola",
    "judas": "epístola",
    # Poesía y Sabiduría
    "salmos": "poesía", "proverbios": "poesía", "eclesiastés": "poesía",
    "eclesiastes": "poesía", "cantares": "poesía",
    "cantar de los cantares": "poesía", "lamentaciones": "poesía",
    "job": "poesía",
    # Narrativa
    "génesis": "narrativa", "genesis": "narrativa",
    "éxodo": "narrativa", "exodo": "narrativa",
    "números": "narrativa", "numeros": "narrativa",
    "josué": "narrativa", "josue": "narrativa",
    "jueces": "narrativa", "rut": "narrativa",
    "1 samuel": "narrativa", "2 samuel": "narrativa",
    "1 reyes": "narrativa", "2 reyes": "narrativa",
    "1 crónicas": "narrativa", "2 crónicas": "narrativa",
    "1 cronicas": "narrativa", "2 cronicas": "narrativa",
    "esdras": "narrativa", "nehemías": "narrativa", "nehemias": "narrativa",
    "ester": "narrativa", "jonás": "narrativa", "jonas": "narrativa",
    "hechos": "narrativa",
    # Evangelios (narrativa teológica)
    "mateo": "narrativa", "marcos": "narrativa",
    "lucas": "narrativa", "juan": "narrativa",
    # Ley
    "levítico": "ley", "levitico": "ley",
    "deuteronomio": "ley",
    # Profecía
    "isaías": "profecía", "isaias": "profecía",
    "jeremías": "profecía", "jeremias": "profecía",
    "ezequiel": "profecía", "daniel": "profecía",
    "oseas": "profecía", "joel": "profecía", "amós": "profecía", "amos": "profecía",
    "abdías": "profecía", "abdias": "profecía",
    "miqueas": "profecía", "nahúm": "profecía", "nahum": "profecía",
    "habacuc": "profecía", "sofonías": "profecía", "sofonias": "profecía",
    "hageo": "profecía", "zacarías": "profecía", "zacarias": "profecía",
    "malaquías": "profecía", "malaquias": "profecía",
    "apocalipsis": "profecía",
}

class PropositionalService:
    """
    Servicio para formatear texto bíblico en 'Modo Julián' (Análisis Proposicional).
    Utiliza un LLM local (Ollama) para realizar un análisis gramatical inteligente.
    Si Ollama no está disponible, hace un fallback a reglas basadas en expresiones regulares.
    """
    
    def __init__(self):
        # Conectores comunes para el fallback de regex
        self.connectors = r'\b(porque|por tanto|así que|por lo cual|pues|sino|para que|a fin de que|mas|pero|y|o)\b'
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.1"

    @staticmethod
    def detect_genre(book_name: str) -> str:
        """Detecta el género literario del libro bíblico a partir de su nombre."""
        if not book_name:
            return "epístola"  # Default
        normalized = book_name.strip().lower()
        return GENRE_MAP.get(normalized, "epístola")
        
    def format_text(self, text: str) -> str:
        """
        Intenta formatear el texto usando IA local (Ollama). 
        Si falla o hay timeout, usa regex.
        """
        # Limpiar YAML frontmatter si llegara a filtrarse
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].strip()

        prompt = f"""Actúa como un experto en gramática y exégesis bíblica. 
Realiza un Análisis Proposicional estricto del siguiente texto bíblico.
Reglas:
1. NO agregues introducciones, conclusiones, ni explicaciones teológicas.
2. NO modifiques ni una sola palabra del texto bíblico original.
3. Devuelve el texto reformateado separando las cláusulas en líneas diferentes.
4. Las cláusulas principales van al margen izquierdo.
5. Las cláusulas subordinadas deben llevar sangría usando el símbolo "> " de Markdown.
6. Separa las proposiciones basándote en conectores lógicos (porque, por tanto, a fin de que, y, o, pero).

TEXTO A ANALIZAR:
{text}
"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0 # Determinístico
                }
            }
            # Timeout de 25 segundos. Un modelo 8B en local debería procesar un capítulo en ~10-15s
            response = requests.post(self.ollama_url, json=payload, timeout=25)
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                # Validación básica de que no haya respondido basura o cortado
                if result and len(result) > len(text) * 0.5:
                    return result
        except Exception as e:
            print(f"Ollama falló para Análisis Proposicional ({e}). Usando fallback (Regex)...")
            
        return self._format_text_regex(text)

    def analyze_with_lens(self, text: str, book_name: str, level: str = "moderado") -> str:
        """
        Análisis Sintáctico-Gramatical profundo con detección de género y andamiaje adaptativo.
        
        Args:
            text: El texto bíblico a analizar.
            book_name: Nombre del libro bíblico (para detectar género).
            level: Nivel de estudio del usuario (principiante, moderado, complejo).
        
        Returns:
            Análisis formateado en Markdown.
        """
        genre = self.detect_genre(book_name)
        
        # Construir instrucciones específicas por género
        genre_instructions = self._get_genre_instructions(genre)
        
        # Construir instrucciones de andamiaje por nivel
        scaffolding_instructions = self._get_scaffolding_instructions(level, genre)
        
        prompt = f"""Actúa como un profesor de hermenéutica y exégesis bíblica de un seminario reformado.
Realiza un ANÁLISIS SINTÁCTICO-GRAMATICAL completo del siguiente texto bíblico.

GÉNERO LITERARIO DETECTADO: {genre.upper()}

{genre_instructions}

NIVEL DE ANDAMIAJE: {level.upper()}
{scaffolding_instructions}

FORMATO DE SALIDA (Markdown estricto):
- Usa encabezados ### para cada sección del análisis.
- Usa **negrita** para resaltar elementos clave (según las instrucciones de nivel).
- Usa `código` para los conectores lógicos y preposiciones clave.
- Usa > (blockquote) para las cláusulas subordinadas o indentadas.
- NO inventes contenido teológico. Solo analiza la gramática y estructura del texto.

TEXTO A ANALIZAR:
{text}
"""
        # Intentar con Ollama primero, luego con Gemini como fallback
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            }
            response = requests.post(self.ollama_url, json=payload, timeout=40)
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                if result and len(result) > 50:
                    return result
        except Exception as e:
            print(f"Ollama falló para Lente Sintáctico ({e}). Intentando con Gemini...")
        
        # Fallback a Gemini vía RAGService._call_llm
        try:
            from services.rag_service import RAGService
            rag = RAGService()
            return rag._call_llm(prompt)
        except Exception as e:
            return f"Error: No se pudo conectar con ningún modelo de IA. Detalle: {str(e)}"
    
    def _get_genre_instructions(self, genre: str) -> str:
        """Devuelve instrucciones de análisis específicas según el género literario."""
        instructions = {
            "epístola": """INSTRUCCIONES PARA EPÍSTOLA (Método de 5 Pasos Proposicionales):
Paso 1 — Identificar cláusulas principales y subordinadas:
  - Separa cada oración en cláusula principal (sujeto + verbo) y cláusulas dependientes.
  - Muestra la jerarquía usando indentación (> para subordinadas).
Paso 2 — Analizar verbos imperativos:
  - Identifica todos los verbos imperativos (órdenes, exhortaciones).
  - Indica quién es el sujeto receptor y qué acción se ordena.
Paso 3 — Identificar preposiciones clave y conectores lógicos:
  - Marca las preposiciones clave (en, con, por, para) que indican relaciones.
  - Marca los conectores lógicos (porque, por tanto, pero, sino, a fin de que, pues).
Paso 4 — Analizar relaciones entre cláusulas:
  - Identifica relaciones: causalidad, consecuencia, contraste, propósito, condición.
Paso 5 — Síntesis estructural:
  - Resume la cadena lógica del argumento del autor en 2-3 oraciones.""",

            "poesía": """INSTRUCCIONES PARA POESÍA HEBREA:
Paso 1 — Identificar paralelismos:
  - Sinónimo: La segunda línea repite la idea de la primera con distintas palabras.
  - Antitético: La segunda línea contrasta con la primera (ej. "pero", "mas").
  - Sintético: La segunda línea completa o expande la idea de la primera.
Paso 2 — Identificar figuras retóricas:
  - Metáforas, símiles, personificaciones, hipérboles, metonimias.
Paso 3 — Estructura estrófica:
  - Agrupa los versículos en estrofas temáticas.
  - Identifica si hay un quiasmo (estructura A-B-B'-A') o inclusio.
Paso 4 — Verbos y tiempos:
  - Identifica verbos clave y sus tiempos (perfecto, imperfecto hebreo si aplica).
Paso 5 — Síntesis:
  - Resume el movimiento emocional/teológico del poema.""",

            "narrativa": """INSTRUCCIONES PARA NARRATIVA BÍBLICA:
Paso 1 — Estructura del relato:
  - Identifica: Exposición, Nudo, Clímax, Desenlace.
Paso 2 — Marcadores de discurso:
  - Identifica fórmulas narrativas ("y aconteció que", "he aquí", "entonces").
  - Marca transiciones temporales y espaciales.
Paso 3 — Discurso directo vs. narración:
  - Distingue lo que dice el narrador de lo que dicen los personajes.
  - Analiza los verbos de habla ("dijo", "respondió", "clamó").
Paso 4 — Repeticiones y patrones:
  - Identifica palabras clave repetidas (Leitwort/palabra guía).
  - Busca patrones numéricos o estructurales.
Paso 5 — Síntesis teológica del narrador:
  - ¿Qué está comunicando el narrador sobre Dios a través de los eventos?""",

            "profecía": """INSTRUCCIONES PARA LITERATURA PROFÉTICA:
Paso 1 — Fórmulas proféticas:
  - Identifica: "Así dice Jehová", "Palabra del Señor", "He aquí", "Oráculo".
Paso 2 — Estructura de oráculos:
  - Distingue: oráculos de juicio vs. oráculos de salvación.
  - Identifica: acusación, sentencia, promesa de restauración.
Paso 3 — Tiempo verbal y cumplimiento:
  - Analiza si los verbos apuntan a cumplimiento cercano, lejano, o doble.
Paso 4 — Imágenes y simbolismo:
  - Identifica las metáforas proféticas recurrentes (viña, esposa infiel, pastor, remanente).
Paso 5 — Síntesis:
  - Resume el mensaje central del oráculo.""",

            "ley": """INSTRUCCIONES PARA LITERATURA LEGAL:
Paso 1 — Tipo de ley:
  - Identifica si es ley apodíctica ("No matarás") o casuística ("Si un hombre...entonces").
Paso 2 — Estructura condicional:
  - Separa la prótasis (condición: "Si...") de la apódosis (consecuencia: "entonces...").
Paso 3 — Sujetos y destinatarios:
  - ¿A quién se dirige la ley? ¿Quién es responsable de cumplirla?
Paso 4 — Sanciones y motivaciones:
  - Identifica las consecuencias por incumplimiento y las motivaciones teológicas ("porque Jehová tu Dios...").
Paso 5 — Síntesis:
  - Resume el principio moral/teológico subyacente detrás de la regulación.""",
        }
        return instructions.get(genre, instructions["epístola"])
    
    def _get_scaffolding_instructions(self, level: str, genre: str) -> str:
        """Devuelve instrucciones de andamiaje según el nivel del usuario."""
        if level == "principiante":
            return """ANDAMIAJE MÁXIMO (el profesor guía paso a paso):
- Resalta TODOS los verbos imperativos/clave en **negrita**.
- Resalta TODOS los conectores lógicos y preposiciones clave en `código inline`.
- Después de cada paso del análisis, incluye una EXPLICACIÓN DIDÁCTICA breve (1-2 oraciones) de por qué ese elemento es importante.
- Al final, incluye un RESUMEN VISUAL de la estructura lógica usando flechas o viñetas que muestren la cadena argumental.
- Usa un tono cálido y didáctico, como un profesor paciente."""

        elif level == "moderado":
            return """ANDAMIAJE MEDIO (el profesor señala, pero no explica todo):
- Resalta los verbos imperativos/clave en **negrita**.
- Resalta los conectores lógicos en `código inline`.
- NO incluyas explicaciones didácticas de cada paso. Solo muestra los resultados del análisis.
- Al final, incluye una pregunta abierta para que el usuario reflexione sobre la estructura que acaba de ver.
- Tono directo y académico."""

        else:  # complejo
            return """ANDAMIAJE MÍNIMO (el profesor desafía):
- NO resaltes verbos ni conectores. Solo separa las cláusulas en líneas diferentes con indentación para subordinadas.
- NO incluyas explicaciones ni etiquetas de relaciones.
- Al final, incluye 2-3 preguntas desafiantes tipo examen:
  - "¿Cuál es el conector lógico que une la cláusula X con la Y?"
  - "¿Qué tipo de relación hay entre las proposiciones 1 y 3?"
  - "¿Cuál es la proposición principal de la que dependen las demás?"
- Tono austero y exigente, como un examen de seminario."""

    def _format_text_regex(self, text: str) -> str:
        """
        Fallback original: divide párrafos largos usando signos de puntuación
        y conectores, facilitando el estudio exegético.
        """
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            if not line.strip():
                continue
                
            if line.startswith('#'):
                formatted_lines.append(line + "\n")
                continue
                
            verse_match = re.match(r'^(\*\*\d+\*\*)\s*(.*)', line.strip())
            if verse_match:
                verse_marker = verse_match.group(1)
                content = verse_match.group(2)
            else:
                verse_marker = ""
                content = line.strip()
                
            content = re.sub(r'\s+', ' ', content)
            content = re.sub(r'([.;:])\s+', r'\1\n  ', content)
            content = re.sub(r',\s*' + self.connectors, r',\n    \1', content, flags=re.IGNORECASE)
            
            propositions = content.split('\n')
            if verse_marker:
                formatted_lines.append(f"{verse_marker} {propositions[0].strip()}")
                for prop in propositions[1:]:
                    if prop.strip():
                        formatted_lines.append(f"> {prop.rstrip()}")
            else:
                for prop in propositions:
                    if prop.strip():
                        formatted_lines.append(f"{prop.rstrip()}")
                        
            formatted_lines.append("") 
            
        return "\n".join(formatted_lines)

