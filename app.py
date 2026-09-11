from pathlib import Path
import os
import re
import html as html_lib

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, abort

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "mfc_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD")

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")


def get_db():
    """Создаёт подключение к PostgreSQL."""
    if not PG_PASSWORD:
        raise RuntimeError("Не задан PG_PASSWORD в .env")

    return psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
        row_factory=dict_row,
    )


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def find_services(question, limit=5):
    """
    Поиск услуг в PostgreSQL.
    Используем ILIKE вместо SQLite LIKE.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                service_title_text,
                documents_text,
                payment_info_text,
                time_term_text,
                service_result_text,
                reject_reasons_text
            FROM services
            WHERE service_title_text ILIKE %s
            ORDER BY service_title_text
            LIMIT %s
            """,
            (f"%{question}%", limit),
        ).fetchall()

        if rows:
            return rows

        words = [
            word
            for word in re.findall(
                r"[А-Яа-яЁёA-Za-z0-9]+",
                question.lower()
            )
            if len(word) >= 4
        ][:8]

        if not words:
            return []

        where = " OR ".join(
            ["service_title_text ILIKE %s"] * len(words)
        )
        params = [f"%{word}%" for word in words]

        return conn.execute(
            f"""
            SELECT
                id,
                service_title_text,
                documents_text,
                payment_info_text,
                time_term_text,
                service_result_text,
                reject_reasons_text
            FROM services
            WHERE {where}
            ORDER BY service_title_text
            LIMIT %s
            """,
            [*params, limit],
        ).fetchall()


def build_context(rows):
    parts = []

    for row in rows:
        parts.append(
            "\n".join(
                [
                    f"Название услуги: {row['service_title_text']}",
                    f"Документы: {clean_html(row.get('documents_text')) or 'Не указано'}",
                    f"Оплата: {clean_html(row.get('payment_info_text')) or 'Не указано'}",
                    f"Срок: {clean_html(row.get('time_term_text')) or 'Не указано'}",
                    f"Результат: {clean_html(row.get('service_result_text')) or 'Не указано'}",
                    f"Основания отказа: {clean_html(row.get('reject_reasons_text')) or 'Не указано'}",
                ]
            )
        )

    return "\n\n---\n\n".join(parts)


def ask_gigachat(question, rows):
    if not GIGACHAT_CREDENTIALS:
        raise RuntimeError(
            "Не найден GIGACHAT_CREDENTIALS в файле .env"
        )

    context = build_context(rows)

    prompt = f"""
Ты — цифровой помощник МФЦ Тульской области.

Отвечай только на основе данных из базы МФЦ, переданных ниже.

Правила:
1. Не придумывай документы.
2. Не придумывай сроки.
3. Не придумывай стоимость.
4. Не придумывай порядок получения.
5. Не придумывай основания отказа.
6. Если данных недостаточно, прямо скажи об этом.
7. Отвечай на русском языке.
8. Отвечай кратко и понятно.

Вопрос пользователя:
{question}

Данные базы МФЦ:
{context or "Подходящая услуга не найдена."}
"""

    with GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=GIGACHAT_CREDENTIALS,
        scope=GIGACHAT_SCOPE,
        verify_ssl_certs=False,
    ) as client:
        chat = Chat(
            model="GigaChat-3-Ultra",
            messages=[
                Messages(
                    role=MessagesRole.USER,
                    content=prompt,
                )
            ],
        )
        response = client.chat(chat)

    return response.choices[0].message.content


@app.route("/")
def index():
    with get_db() as conn:
        groups = conn.execute(
            """
            SELECT id, group_key, name
            FROM classification_groups
            ORDER BY id
            """
        ).fetchall()

        services_count = conn.execute(
            "SELECT COUNT(*) AS c FROM services"
        ).fetchone()["c"]

        categories_count = conn.execute(
            "SELECT COUNT(*) AS c FROM classification_categories"
        ).fetchone()["c"]

    return render_template(
        "index.html",
        groups=groups,
        services_count=services_count,
        categories_count=categories_count,
    )


@app.get("/api/categories")
def api_categories():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                cg.id AS group_id,
                cg.name AS group_name,
                cc.id AS category_id,
                cc.source_id,
                cc.name AS category_name
            FROM classification_groups cg
            LEFT JOIN classification_categories cc
                ON cc.group_id = cg.id
            ORDER BY cg.id, cc.name
            """
        ).fetchall()

    groups = {}

    for row in rows:
        key = str(row["group_id"])

        if key not in groups:
            groups[key] = {
                "id": row["group_id"],
                "name": row["group_name"],
                "categories": [],
            }

        if row["category_id"] is not None:
            groups[key]["categories"].append(
                {
                    "id": row["category_id"],
                    "source_id": row["source_id"],
                    "name": row["category_name"],
                }
            )

    return jsonify(list(groups.values()))


@app.get("/api/services")
def api_services():
    query = (request.args.get("q") or "").strip()

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    limit = min(max(limit, 1), 100)

    with get_db() as conn:
        if query:
            rows = conn.execute(
                """
                SELECT
                    id,
                    service_title_text,
                    payment_info_text,
                    time_term_text,
                    documents_text
                FROM services
                WHERE service_title_text ILIKE %s
                ORDER BY service_title_text
                LIMIT %s
                """,
                (f"%{query}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    id,
                    service_title_text,
                    payment_info_text,
                    time_term_text,
                    documents_text
                FROM services
                ORDER BY service_title_text
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

    return jsonify(
        [
            {
                "id": row["id"],
                "name": row["service_title_text"],
                "payment": clean_html(row.get("payment_info_text")),
                "time": clean_html(row.get("time_term_text")),
                "documents": clean_html(row.get("documents_text")),
            }
            for row in rows
        ]
    )


@app.get("/api/services/<service_id>")
def api_service(service_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM services WHERE id = %s",
            (service_id,),
        ).fetchone()

        if row is None:
            abort(404)

        refs = conn.execute(
            """
            SELECT classification_group, classification_category_id
            FROM service_classification_refs
            WHERE source_service_ref = %s
            LIMIT 50
            """,
            (service_id,),
        ).fetchall()

    service = dict(row)

    for field in (
        "service_recipients",
        "documents_text",
        "payment_info_text",
        "time_term_text",
        "service_result_text",
        "description_text",
        "reject_reasons_text",
    ):
        service[field] = clean_html(service.get(field))

    service["classification_refs"] = [dict(ref) for ref in refs]
    return jsonify(service)


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()

    if not question:
        return jsonify({"error": "Пустой запрос"}), 400

    try:
        rows = find_services(question, limit=5)
        answer = ask_gigachat(question, rows)

        return jsonify(
            {
                "answer": answer,
                "matched": [row["service_title_text"] for row in rows],
                "source": "postgresql",
            }
        )

    except Exception as exc:
        print("APP ERROR:", repr(exc))
        return jsonify(
            {
                "error": "Ошибка сервера",
                "details": str(exc),
            }
        ), 500


if __name__ == "__main__":
    # Проверяем PostgreSQL до запуска Flask.
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        print("PostgreSQL: подключение успешно")
    except Exception as exc:
        print("PostgreSQL ERROR:", repr(exc))
        raise

    app.run(debug=True)
