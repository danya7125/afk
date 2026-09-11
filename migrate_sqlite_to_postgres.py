import sqlite3
import psycopg2
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "data" / "mfc_data.db"

PG_HOST = "127.0.0.1"
PG_PORT = 5432
PG_DATABASE = "mfc_data"
PG_USER = "postgres"
PG_PASSWORD = "psg_123"


TABLES = [
    "classification_groups",
    "classification_categories",
    "services",
    "service_classification_refs",
    "document_files",
    "legal_act_files",
    "other_documents",
]


def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_postgres_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )


def create_tables(pg_conn):
    cursor = pg_conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classification_groups (
            id INTEGER PRIMARY KEY,
            group_key TEXT NOT NULL,
            name TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classification_categories (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            name TEXT NOT NULL,
            uuid_smart_line TEXT,
            schedule_json TEXT,
            address TEXT,
            area_size DOUBLE PRECISION,
            chief_name TEXT,
            chief_post TEXT,
            code TEXT,
            queue_host TEXT,
            window_count INTEGER
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            life_situation_ids_json TEXT NOT NULL,
            mfc_ids_json TEXT NOT NULL,
            recipient_ids_json TEXT NOT NULL,
            department_id TEXT,
            service_title_text TEXT NOT NULL,
            service_ordering_text TEXT,
            service_recipients TEXT,
            applicant_categories_json TEXT,
            documents_text TEXT,
            payment_info_text TEXT,
            time_term_text TEXT,
            service_result_text TEXT,
            description_text TEXT,
            reject_reasons_text TEXT
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_classification_refs (
            id INTEGER PRIMARY KEY,
            classification_group TEXT NOT NULL,
            classification_category_id INTEGER NOT NULL,
            source_service_ref TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_files (
            id INTEGER PRIMARY KEY,
            service_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_act_files (
            id INTEGER PRIMARY KEY,
            service_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS other_documents (
            id INTEGER PRIMARY KEY,
            service_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
    """)

    pg_conn.commit()
    cursor.close()


def copy_table(sqlite_conn, pg_conn, table_name):
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()

    rows = sqlite_cursor.execute(
        f'SELECT * FROM "{table_name}"'
    ).fetchall()

    if not rows:
        print(f"{table_name}: 0 записей")
        return

    columns = rows[0].keys()

    column_names = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    sql = f"""
        INSERT INTO "{table_name}" ({column_names})
        VALUES ({placeholders})
        ON CONFLICT (id) DO NOTHING
    """

    for row in rows:
        values = tuple(row[column] for column in columns)
        pg_cursor.execute(sql, values)

    pg_conn.commit()

    print(f"{table_name}: перенесено {len(rows)} записей")


def main():
    if not SQLITE_DB.exists():
        raise FileNotFoundError(
            f"Не найдена SQLite база: {SQLITE_DB}"
        )

    print("Подключение к SQLite...")
    sqlite_conn = get_sqlite_connection()

    print("Подключение к PostgreSQL...")
    pg_conn = get_postgres_connection()

    try:
        print("Создание таблиц PostgreSQL...")
        create_tables(pg_conn)

        print("\nПеренос данных:")

        for table in TABLES:
            copy_table(sqlite_conn, pg_conn, table)

        print("\nМиграция завершена успешно.")

    except Exception:
        pg_conn.rollback()
        raise

    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()