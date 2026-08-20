import pytest
from services.propositional_service import PropositionalService

def test_format_text_separates_connectors():
    svc = PropositionalService()
    text = "Dios es amor, porque Él nos amó primero; por tanto, amémonos."
    formatted = svc.format_text(text)
    
    # "porque" y "por tanto" son conectores.
    # El servicio debería ponerlos en nuevas líneas o indentarlos.
    assert "porque" in formatted.lower()
    assert "\n" in formatted # Debería haber saltos de línea introducidos
    
def test_format_text_preserves_verses():
    svc = PropositionalService()
    text = "**1** En el principio creó Dios los cielos y la tierra."
    formatted = svc.format_text(text)
    
    assert "**1**" in formatted
    assert "En el principio" in formatted
