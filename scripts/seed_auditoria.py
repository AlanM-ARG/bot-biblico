import sqlite3
import os

DB_PATH = 'biblico.db'

def inyectar_lista_deseados():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    libros_deseados = [
        # --- Los diez libros que todo cristiano debería leer ---
        ("El Dios pródigo", "Tim Keller"),
        ("Dioses que fallan", "Tim Keller"),
        ("Sexo y dinero", "Paul Tripp"),
        ("Guerra de palabras", "Paul Tripp"),
        ("El asombro del perdón", "José de Segovia"),
        ("El pacificador", "Ken Sande"),
        ("Los afectos religiosos", "Jonathan Edwards"),
        ("Cuando no deseo a Dios", "John Piper"),
        ("Sobre la tentación", "John Owen"),
        ("Mero cristianismo", "C.S. Lewis"),
        
        # --- Los diez mejores AUTORES CRISTIANOS ---
        ("Obras Generales", "Tim Keller"),
        ("Obras Generales", "Paul Tripp"),
        ("Obras Generales", "John Piper"),
        ("Obras Generales", "C. S. Lewis"),
        ("Obras Generales", "Jonathan Edwards"),
        ("Obras Generales", "John Owen"),
        ("Obras Generales", "Philip Yancey"),
        ("Obras Generales", "A. W. Tozer"),
        ("Obras Generales", "John Stott"),
        ("Obras Generales", "Martyn Lloyd Jones"),

        # --- Los diez libros para crecer en tu VIDA ESPIRITUAL ---
        ("Disciplinas espirituales para la vida cristiana", "Donald S. Whitney"),
        ("Alabanza a la disciplina", "Richard Foster"),
        ("La búsqueda de Dios", "A. W. Tozer"),
        ("Cartas de un diablo a su sobrino", "C.S. Lewis"),
        ("El conocimiento del Dios santo", "J. I. Packer"),
        ("La práctica de la presencia de Dios", "El hermano Lorenzo"),
        ("Radical", "David Platt"),
        ("La mortificación del pecado", "John Owen"),
        ("Gracia divina vs condena humana", "Philip Yancey"),
        ("Autoolvido", "Tim Keller"),

        # --- Tres libros preciosos sobre la ORACIÓN ---
        ("La oración", "Tim Keller"),
        ("La oración, ¿hace alguna diferencia?", "Philip Yancey"),
        ("La escuela de la oración", "Andrew Murray"),

        # --- Cinco BIOGRAFÍAS que te inspiran ---
        ("El secreto Espiritual de Hudson Taylor", "Howard y Geraldine Taylor"),
        ("Torturado por Cristo", "Richard Wurmbrand"),
        ("El diario de David Brainerd", "Oswald Smith"),
        ("Torturado por su fe", "Halaran Popov"),
        ("Un hombre de fe", "Jorge Muller"),

        # --- Dos recursos esenciales para ESTUDIAR LA BIBLIA ---
        ("Treinta días para entender la Biblia", "Max Anders"),
        ("Interpretación bíblica", "Howard. G. Hendricks"),

        # --- Cuatro autores recomendables sobre CONSEJERÍA BÍBLICA ---
        ("Consejería Bíblica (Obras Generales)", "Paul Tripp"),
        ("Consejería Bíblica (Obras Generales)", "David Powlison"),
        ("Consejería Bíblica (Obras Generales)", "Elyse Fitzpatrick"),
        ("Consejería Bíblica (Obras Generales)", "Edward T. Welch"),

        # --- Los seis mejores libros sobre CRIANZA DE NIÑOS ---
        ("La crianza de los hijos", "Paul Tripp"),
        ("Give them grace", "Elyse Fitzpatrick"),
        ("Sacred parenting", "Gary Thomas"),
        ("Pastoreando el corazón de tu hijo", "Tedd Tripp"),
        ("Como instruir el corazón de tu hijo", "Tedd Tripp"),
        ("Edad de la oportunidad", "Paul Tripp"),

        # --- Los seis mejores libros sobre MATRIMONIO ---
        ("¿Qué estabas esperando?", "Paul Tripp"),
        ("Matrimonio Sagrado", "Gary Thomas"),
        ("Los cinco lenguajes del amor", "Gary Chapman"),
        ("Pacto matrimonial", "John Piper"),
        ("El significado del matrimonio", "Tim Keller"),
        ("Cuando pecadores dicen: \"Acepto\"", "Dave Harvey"),

        # --- Cuatro libros excelentes sobre EVANGELISMO y DISCIPULADO ---
        ("El plan maestro de evangelización", "Robert Coleman"),
        ("Manual de evangelización para el siglo XXI", "David Burt"),
        ("El enrejado y la vid", "Collin Marshall y Tony Payne"),
        ("Manual Ministerial de Evangelismo", "Nicolás Tranchini"),

        # --- Cinco libros de DEVOCIONALES ---
        ("En pos de lo supremo", "Oswald Chambers"),
        ("Misericordias nuevas cada mañana", "Paul Tripp"),
        ("Alza tus ojos", "Chris Shaw"),
        ("Lecturas matutinas", "Charles Spurgeon"),
        ("Los cantos de Jesús", "Tim Keller"),

        # --- Dos libros que no puedes dejar de leer si estás LIDERANDO ---
        ("El llamamiento peligroso", "Paul Tripp"),
        ("Hermanos, no somos profesionales", "John Piper"),

        # --- Diez autores sobre preguntas difíciles y APOLOGÉTICA ---
        ("Apologética (Obras Generales)", "Allister McGrath"),
        ("Apologética (Obras Generales)", "Norman Geisler"),
        ("Apologética (Obras Generales)", "Philip Yancey"),
        ("Apologética (Obras Generales)", "Keneth Boa"),
        ("Apologética (Obras Generales)", "C.S. Lewis"),
        ("Apologética (Obras Generales)", "Lee Strobel"),
        ("Apologética (Obras Generales)", "Josh McDowell"),
        ("Apologética (Obras Generales)", "Os Guinnes"),
        ("Apologética (Obras Generales)", "Antonio Cruz"),
        ("Apologética (Obras Generales)", "Ramesh Richard"),

        # --- Dos recursos clave para la IGLESIA ---
        ("Edificando iglesias sanas (Serie completa)", "Mark Dever (y otros 9Marcas)"),
        ("Una vida centrada (Serie completa)", "Tim Chester y otros (Poiema)"),

        # --- Cinco autores para estudiar el SUFRIMIENTO ---
        ("El problema del dolor", "C.S. Lewis"),
        ("Llamados a sufrir", "David Burt"),
        ("Confiando en Dios aunque la vida duela", "Jerry Bridges"),
        ("¿Hasta cuándo, Señor?", "Donald Carson"),
        ("Cuando lo que Dios hace no tiene sentido", "James Dobson"),

        # --- Cinco COMENTARISTAS BÍBLICOS muy recomendados ---
        ("Comentarios Bíblicos (Obras Generales)", "John Stott"),
        ("Comentarios Bíblicos (Obras Generales)", "David Burt"),
        ("Notas Expositivas (Obras Generales)", "Thomas Constable"),
        ("Comentarios Bíblicos (Obras Generales)", "Martyn Lloyd Jones"),
        ("Comentarios Bíblicos (Obras Generales)", "F. F. Bruce"),

        # --- Cinco autores para estudiar TEOLOGÍA ---
        ("Teología (Obras Generales)", "John Stott"),
        ("Teología (Obras Generales)", "J.I. Packer"),
        ("Teología (Obras Generales)", "Wayne Grudem"),
        ("Teología (Obras Generales)", "R.C. Sproul"),
        ("Teología (Obras Generales)", "Edmund P. Clowney"),
    ]
    
    insertados = 0
    for titulo, autor in libros_deseados:
        # Check if already exists to avoid duplicates if run multiple times
        cursor.execute("SELECT id FROM auditoria_libros WHERE titulo = ? AND autor = ?", (titulo, autor))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO auditoria_libros (titulo, autor, categoria, justificacion, estado_revision)
                VALUES (?, ?, 'Pendiente', 'Sugerido para la biblioteca. A la espera de carga del PDF para auditoría.', 'Esperando Archivo PDF')
            """, (titulo, autor))
            insertados += 1
            
    conn.commit()
    conn.close()
    
    print(f"Se han inyectado {insertados} libros en la lista de deseados (estado: Pendiente).")

if __name__ == "__main__":
    # Ensure database is initialized first
    from database.connection import init_db
    init_db()
    inyectar_lista_deseados()
