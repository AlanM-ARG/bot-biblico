import sqlite3
import os

DB_PATH = 'biblico.db'

def get_connection():
    """Returns a connection to the SQLite/LibSQL database."""
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    
    if turso_url:
        import libsql_experimental as libsql
        # Conexión remota a Turso en Producción
        conn = libsql.connect(
            database=turso_url,
            auth_token=os.environ.get("TURSO_AUTH_TOKEN"),
            check_same_thread=False
        )
    else:
        # Conexión local en Desarrollo
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def _add_column_if_missing(cursor, table_name: str, column_name: str, column_def: str):
    """Safely add a column to an existing table if it doesn't exist."""
    if not _column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def _migrate_existing_tables(cursor):
    """Apply migrations to existing tables without losing data."""

    # --- users table migrations ---
    # Note: ALTER TABLE ADD COLUMN in SQLite does not support non-constant
    # defaults like CURRENT_TIMESTAMP. We use NULL for migration defaults;
    # the CREATE TABLE definition handles proper defaults for new rows.
    if _table_exists(cursor, 'users'):
        _add_column_if_missing(cursor, 'users', 'display_name', 'TEXT')
        _add_column_if_missing(cursor, 'users', 'study_level', "TEXT DEFAULT 'principiante'")
        _add_column_if_missing(cursor, 'users', 'family_mode', 'BOOLEAN DEFAULT 0')
        _add_column_if_missing(cursor, 'users', 'vital_context', 'TEXT')
        _add_column_if_missing(cursor, 'users', 'updated_at', 'TIMESTAMP')

    # --- habits table migrations ---
    if _table_exists(cursor, 'habits'):
        _add_column_if_missing(cursor, 'habits', 'meditation', 'BOOLEAN DEFAULT 0')
        _add_column_if_missing(cursor, 'habits', 'family_worship', 'BOOLEAN DEFAULT 0')
        _add_column_if_missing(cursor, 'habits', 'notes', 'TEXT')

    # --- sermons table migrations ---
    if _table_exists(cursor, 'sermons'):
        _add_column_if_missing(cursor, 'sermons', 'preacher', "TEXT DEFAULT 'Desconocido'")
        _add_column_if_missing(cursor, 'sermons', 'resource_id', 'INTEGER')
        _add_column_if_missing(cursor, 'sermons', 'is_vectorized', 'BOOLEAN DEFAULT 0')
        _add_column_if_missing(cursor, 'sermons', 'created_at', 'TIMESTAMP')

    # --- journal_entries table migrations ---
    if _table_exists(cursor, 'journal_entries'):
        _add_column_if_missing(cursor, 'journal_entries', 'created_at', 'TIMESTAMP')


def init_db():
    """Initializes the database with all required tables and applies migrations."""
    conn = get_connection()
    cursor = conn.cursor()

    # =========================================================================
    # DATOS PÚBLICOS (compartidos entre todos los usuarios)
    # =========================================================================

    # Resources — Auditoría de recursos inyectados al sistema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            filepath      TEXT NOT NULL UNIQUE,
            resource_type TEXT NOT NULL,
            category      TEXT DEFAULT 'general',
            md5_hash      TEXT UNIQUE NOT NULL,
            metadata_json TEXT,
            is_vectorized BOOLEAN DEFAULT 0,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Sermons — Predicaciones transcritas (públicas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sermons (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            title         TEXT NOT NULL,
            preacher      TEXT DEFAULT 'Desconocido',
            date          DATE NOT NULL,
            md5_hash      TEXT UNIQUE NOT NULL,
            transcription TEXT NOT NULL,
            resource_id   INTEGER,
            is_vectorized BOOLEAN DEFAULT 0,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources (id)
        )
    ''')

    # Cache Audit — Control de invalidación de guías generadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache_audit (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            guide_key       TEXT NOT NULL UNIQUE,
            generated_at    TIMESTAMP NOT NULL,
            file_path       TEXT NOT NULL,
            is_stale        BOOLEAN DEFAULT 0,
            invalidated_at  TIMESTAMP
        )
    ''')

    # OpenBible Cross References
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_references (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source_verse  TEXT NOT NULL,
            target_verse  TEXT NOT NULL,
            votes         INTEGER DEFAULT 0
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_source ON cross_references(source_verse)")

    # Auditoría Doctrinal de Libros
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auditoria_libros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            categoria TEXT CHECK(categoria IN ('Alineado', 'Precaución', 'Descartar', 'Pendiente')) DEFAULT 'Pendiente',
            justificacion TEXT,
            estado_revision TEXT DEFAULT 'Esperando Archivo PDF',
            resource_id INTEGER,
            FOREIGN KEY (resource_id) REFERENCES resources(id)
        )
    ''')

    # Temas Pendientes (Backlog detectado por IA)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temas_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema_o_libro TEXT NOT NULL,
            motivo_necesidad TEXT,
            tipo_recurso_requerido TEXT,
            estado TEXT DEFAULT 'Pendiente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # =========================================================================
    # DATOS PRIVADOS (aislados por user_id)
    # =========================================================================

    # Users — Perfiles con nivel de estudio y modo familiar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            display_name    TEXT,
            study_level     TEXT DEFAULT 'principiante',
            family_mode     BOOLEAN DEFAULT 0,
            vital_context   TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Habits — Tracker de Gracia (extendido)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            date            DATE NOT NULL,
            bible_reading   BOOLEAN DEFAULT 0,
            prayer          BOOLEAN DEFAULT 0,
            meditation      BOOLEAN DEFAULT 0,
            family_worship  BOOLEAN DEFAULT 0,
            notes           TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')

    # Journal Entries — Diario espiritual
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                 INTEGER NOT NULL,
            date                    DATE NOT NULL,
            humiliation             TEXT,
            christ                  TEXT,
            practical_application   TEXT,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Reading progress and user notes tables were deprecated.

    # User Roadmaps — Planes de estudio generados por IA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_roadmaps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            topic           TEXT NOT NULL,
            roadmap_json    TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')


    # =========================================================================
    # MÓDULO FEEDBACK BETA
    # =========================================================================

    # Feedback — Sugerencias y reportes de bugs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            type        TEXT NOT NULL DEFAULT 'sugerencia',
            message     TEXT NOT NULL,
            page        TEXT,
            status      TEXT DEFAULT 'pendiente',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # =========================================================================
    # MIGRACIONES — Agregar columnas nuevas a tablas existentes sin perder datos
    # =========================================================================
    _migrate_existing_tables(cursor)

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print("Database initialized successfully with full multi-user schema.")
