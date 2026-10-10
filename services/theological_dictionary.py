import re
import sqlite3
from typing import Dict
from database.connection import DB_PATH

class TheologicalDictionary:
    """
    Servicio de Diccionario Teológico.
    Interpreta palabras clave en el texto y las envuelve en tooltips HTML
    (<abbr title="Definición">Palabra</abbr>) para que Streamlit las renderice.
    Busca primero en la tabla `dictionary` y luego tiene un diccionario base hardcodeado por si acaso.
    """
    _base_dict = {
        "propiciación": "Acción mediante la cual se satisface la ira de Dios por el pecado a través del sacrificio de Cristo.",
        "soteriología": "Rama de la teología que estudia la salvación.",
        "expiación": "Eliminación de la culpa o el pecado; acto de purificación.",
        "regeneración": "El nuevo nacimiento obra del Espíritu Santo, que da vida espiritual al pecador.",
        "santificación": "Proceso continuo mediante el cual el Espíritu Santo hace al creyente más santo y semejante a Cristo.",
        "justificación": "Acto legal de Dios por el cual declara justo al pecador sobre la base de la justicia imputada de Cristo.",
        "escatología": "Rama de la teología que estudia las últimas cosas o los tiempos del fin.",
        "hermenéutica": "Ciencia y arte de la interpretación de textos, especialmente de la Biblia.",
        "exégesis": "Extracción cuidadosa del significado del texto bíblico a partir del texto mismo, considerando su contexto original."
    }

    @classmethod
    def get_dictionary(cls) -> Dict[str, str]:
        """Carga el diccionario combinando la base con la BD SQLite."""
        full_dict = cls._base_dict.copy()
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT term, definition FROM dictionary")
            rows = cursor.fetchall()
            for term, definition in rows:
                full_dict[term.lower()] = definition
            conn.close()
        except Exception:
            pass
        return full_dict

    @classmethod
    def highlight_terms(cls, text: str) -> str:
        """Busca términos teológicos y los envuelve en etiquetas <abbr>."""
        if not text:
            return text
            
        dictionary = cls.get_dictionary()
        
        # Ordenamos por longitud descendente para evitar que 'expiación' pise a 'día de expiación' si lo hubiera
        terms = sorted(dictionary.keys(), key=len, reverse=True)
        
        result_text = text
        for term in terms:
            definition = dictionary[term]
            # Regex que busca la palabra exacta respetando bordes, case-insensitive
            # Evita reemplazar dentro de otras etiquetas HTML ya existentes (esto es un regex básico, podría fallar si hay HTML complejo)
            pattern = re.compile(rf'\b({term})\b', flags=re.IGNORECASE)
            
            # Reemplazamos manteniendo el caso original de la palabra escrita por el LLM
            replacement = rf'<abbr title="{definition}">\1</abbr>'
            result_text = pattern.sub(replacement, result_text)
            
        return result_text
