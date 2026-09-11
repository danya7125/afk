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
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def find_services(question, limit=5):
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
            for word in re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", question.lower())
            if len(word) >= 4
        ][:8]

        if not words:
            return []

        where = " OR ".join(["service_title_text ILIKE %s"] * len(words))
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
        raise RuntimeError("Не найден GIGACHAT_CREDENTIALS в файле .env")

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
        services_count = conn.execute(
            "SELECT COUNT(*) AS c FROM services"
        ).fetchone()["c"]

    categories = [
        {"id": "documents", "name": "Документы и паспорта"},
        {"id": "registration", "name": "Регистрация и место жительства"},
        {"id": "real_estate", "name": "Недвижимость и земля"},
        {"id": "transport", "name": "Транспорт"},
        {"id": "social", "name": "Социальные выплаты и льготы"},
        {"id": "family", "name": "Семья и дети"},
        {"id": "civil", "name": "ЗАГС"},
        {"id": "tax", "name": "Налоги"},
        {"id": "housing", "name": "Жильё и коммунальные услуги"},
        {"id": "business", "name": "Бизнес и предпринимательство"},
        {"id": "certificates", "name": "Справки и сведения"},
        {"id": "other", "name": "Прочие услуги"},
    ]

    return render_template(
        "index.html",
        categories=categories,
        services_count=services_count,
        categories_count=len(categories),
    )

@app.get("/api/categories")
def api_categories():
    return jsonify([
        {"id": "documents", "name": "Документы и паспорта"},
        {"id": "registration", "name": "Регистрация и место жительства"},
        {"id": "real_estate", "name": "Недвижимость и земля"},
        {"id": "transport", "name": "Транспорт"},
        {"id": "social", "name": "Социальные выплаты и льготы"},
        {"id": "family", "name": "Семья и дети"},
        {"id": "civil", "name": "ЗАГС"},
        {"id": "tax", "name": "Налоги"},
        {"id": "housing", "name": "Жильё и коммунальные услуги"},
        {"id": "business", "name": "Бизнес и предпринимательство"},
        {"id": "certificates", "name": "Справки и сведения"},
        {"id": "other", "name": "Прочие услуги"},
    ])

@app.get("/api/services")
def api_services():
    query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    status = (request.args.get("status") or "").strip()

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100

    limit = min(max(limit, 1), 1000)

    conditions = []
    params = []

    if query:
        conditions.append("s.service_title_text ILIKE %s")
        params.append(f"%{query}%")

    category_terms = {
        "documents": ["паспорт", "загранпаспорт", "гражданств", "удостоверен", "миграц"],
        "registration": ["регистрац", "место жительств", "пребыва", "пропис"],
        "real_estate": ["недвиж", "квартир", "жилым помещ", "домом", "земель", "земл", "кадастр", "егрн", "имуществен"],
        "transport": ["автомоб", "транспорт", "тс ", "регистрац.*тс", "водитель", "парков", "прицеп"],
        "social": ["пенси", "пособ", "льгот", "социальн", "материнск", "инвалид", "компенсац"],
        "family": ["ребен", "семь", "многодет", "опек", "усынов", "материнск", "алим"],
        "civil": ["загс", "рождени", "смерт", "брака", "брак", "развод", "отцовств", "имя"],
        "tax": ["налог", "ндфл", "деклараци", "налогооблож", "фнс", "ип"],
        "housing": ["жкх", "жилищ", "коммунал", "капитальн ремонт", "субсид", "электроэнерг", "газоснабжен"],
        "business": ["предприним", "бизнес", "юридическ лиц", "ип ", "лиценз", "разрешен", "торговл"],
        "certificates": ["справк", "выписк", "сведени", "подтвержден", "документ"],
    }

    if category and category in category_terms:
        terms = category_terms[category]
        term_conditions = []
        for term in terms:
            term_conditions.append("COALESCE(s.service_title_text, '') ILIKE %s")
            params.append(f"%{term}%")
        conditions.append("(" + " OR ".join(term_conditions) + ")")
    elif category == "other":
        known_terms = [
            t for values in category_terms.values() for t in values
        ]
        other_parts = []
        for term in known_terms:
            other_parts.append("COALESCE(s.service_title_text, '') NOT ILIKE %s")
            params.append(f"%{term}%")
        if other_parts:
            conditions.append(" AND ".join(other_parts))

    if status == "with_time":
        conditions.append(
            """
            length(
                btrim(
                    regexp_replace(COALESCE(s.time_term_text, ''), '<[^>]*>', '', 'g')
                )
            ) > 0
            """
        )
    elif status == "with_documents":
        conditions.append(
            """
            length(
                btrim(
                    regexp_replace(COALESCE(s.documents_text, ''), '<[^>]*>', '', 'g')
                )
            ) > 0
            """
        )
    elif status == "with_payment":
        conditions.append(
            """
            length(
                btrim(
                    regexp_replace(COALESCE(s.payment_info_text, ''), '<[^>]*>', '', 'g')
                )
            ) > 0
            """
        )

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                s.id,
                s.service_title_text,
                s.payment_info_text,
                s.time_term_text,
                s.documents_text
            FROM services s
            {where_sql}
            ORDER BY s.service_title_text
            LIMIT %s
            """,
            [*params, limit],
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
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        print("PostgreSQL: подключение успешно")
    except Exception as exc:
        print("PostgreSQL ERROR:", repr(exc))
        raise

    app.run(debug=True)
