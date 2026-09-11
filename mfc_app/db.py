from flask import current_app
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def init_pool() -> None:
    global _pool

    if _pool is not None:
        return

    password = current_app.config.get("PG_PASSWORD")
    if not password:
        raise RuntimeError("Не задан PG_PASSWORD в .env")

    conninfo = (
        f"host={current_app.config['PG_HOST']} "
        f"port={current_app.config['PG_PORT']} "
        f"dbname={current_app.config['PG_DATABASE']} "
        f"user={current_app.config['PG_USER']} "
        f"password={password} "
        f"connect_timeout={current_app.config['PG_CONNECT_TIMEOUT']}"
    )

    _pool = ConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=10,
        kwargs={
            "row_factory": dict_row,
        },
        open=True,
    )

    _pool.wait()


def get_connection():
    if _pool is None:
        init_pool()

    return _pool.connection()


def close_pool() -> None:
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


def check_connection() -> None:
    with get_connection() as conn:
        conn.execute("SELECT 1")