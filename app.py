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


def normalize_chat_query(question: str) -> str:
    text = (question or "").lower().strip()

    replacements = {
        "загран паспорт": "загранпаспорт",
        "загран. паспорт": "загранпаспорт",
        "загран-паспорт": "загранпаспорт",
        "заграничный паспорт": "загранпаспорт",
        "заграничного паспорта": "загранпаспорт",
        "заграничному паспорту": "загранпаспорт",
        "загранника": "загранпаспорт",
        "загранник": "загранпаспорт",
        "прописка": "регистрация",
        "прописаться": "регистрация",
        "прописать": "регистрация",
        "машина": "автомобиль",
        "тачка": "автомобиль",
        "авто": "автомобиль",
        "права": "водительское удостоверение",
        "пенсионка": "пенсия",
        "детские": "пособия",
        "справка о несудимости": "справка о судимости",
    }

    for old, new in sorted(
        replacements.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    ):
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)

    return text


def extract_service_terms(question: str) -> list[str]:
    """
    Преобразует пользовательский запрос в набор смысловых поисковых терминов.
    Для загранпаспорта учитывает официальную формулировку, которая реально
    используется в базе mfc_data.
    """
    text = normalize_chat_query(question)

    stop_words = {
        "как", "какой", "какая", "какие", "какое",
        "сколько", "стоимость", "цена", "цены",
        "мне", "могу", "можно", "нужно", "нужен", "нужна", "нужны",
        "хочу", "хотел", "хотела", "получить", "получения",
        "оформить", "оформления", "оформление",
        "расскажи", "рассказать", "подскажи", "подскажите",
        "пожалуйста", "для", "при", "по", "на", "в", "с", "из",
        "и", "или", "про", "об", "это",
    }

    words = [
        word
        for word in re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", text)
        if len(word) >= 3 and word not in stop_words
    ]

    result = []

    # ВАЖНО: в mfc_data загранпаспорт называется не "загранпаспорт",
    # а "Оформление и выдача паспортов гражданина Российской Федерации
    # за пределами территории Российской Федерации".
    if "загранпаспорт" in text:
        result.extend([
            "загранпаспорт",
            "загранпаспорта",
            "заграничный паспорт",
            "заграничного паспорта",
            "заграничному паспорту",
            "за пределами территории Российской Федерации",
            "оформление и выдача паспортов гражданина Российской Федерации за пределами территории Российской Федерации",
        ])

    if "регистрация" in text:
        result.extend([
            "регистрация",
            "регистрации",
            "регистрацию",
            "место жительства",
            "месту жительства",
            "постановка на регистрационный учет",
        ])

    if "водительское удостоверение" in text:
        result.extend([
            "водительское удостоверение",
            "водительского удостоверения",
        ])

    if "автомобиль" in text:
        result.extend([
            "автомобиль",
            "автомобиля",
            "транспортное средство",
            "транспортного средства",
            "регистрация транспортного средства",
        ])

    if "паспорт" in text and "загранпаспорт" not in text:
        result.extend([
            "паспорт",
            "паспорта",
            "паспорт гражданина Российской Федерации",
            "выдача паспортов гражданина Российской Федерации",
        ])

    result.extend(words)

    result = list(dict.fromkeys(
        value.strip().lower()
        for value in result
        if value and len(value.strip()) >= 3
    ))

    # Длинные и официальные фразы идут первыми.
    result.sort(key=len, reverse=True)

    return result[:20]


def find_services(question, limit=5):
    """
    Сначала ищет тему услуги по НАЗВАНИЮ.
    Только если по названию ничего не найдено, использует описание/документы.

    Это важно: запрос «сколько стоит загранпаспорт» не должен
    находить чужую услугу только потому, что слово «загранпаспорт»
    встретилось в её списке документов.
    """
    terms = extract_service_terms(question)

    if not terms:
        return []

    with get_db() as conn:
        real_service_filter = """
            s.service_title_text IS NOT NULL
            AND NULLIF(BTRIM(s.service_title_text), '') IS NOT NULL
            AND s.service_title_text <> 'SmevRequestService'
            AND (
                  NULLIF(BTRIM(COALESCE(s.description_text, '')), '') IS NOT NULL
               OR NULLIF(BTRIM(COALESCE(s.documents_text, '')), '') IS NOT NULL
               OR NULLIF(BTRIM(COALESCE(s.payment_info_text, '')), '') IS NOT NULL
               OR NULLIF(BTRIM(COALESCE(s.time_term_text, '')), '') IS NOT NULL
               OR NULLIF(BTRIM(COALESCE(s.service_result_text, '')), '') IS NOT NULL
               OR NULLIF(BTRIM(COALESCE(s.reject_reasons_text, '')), '') IS NOT NULL
            )
        """

        # ШАГ 1. Ищем по названию услуги.
        title_conditions = []
        title_params = []

        for term in terms:
            like = f"%{term}%"
            title_conditions.append("s.service_title_text ILIKE %s")
            title_params.append(like)

        title_rows = conn.execute(
            f"""
            SELECT
                s.id,
                s.service_title_text,
                s.description_text,
                s.documents_text,
                s.payment_info_text,
                s.time_term_text,
                s.service_result_text,
                s.reject_reasons_text
            FROM services s
            WHERE {real_service_filter}
              AND ({" OR ".join(title_conditions)})
            ORDER BY
                CASE
                    WHEN s.service_title_text ILIKE %s THEN 0
                    ELSE 1
                END,
                length(s.service_title_text),
                s.service_title_text
            LIMIT %s
            """,
            [
                *title_params,
                f"%{terms[0]}%",
                limit,
            ],
        ).fetchall()

        if title_rows:
            print(f"SEARCH TITLE HIT: {terms} -> {len(title_rows)}")
            return title_rows

        # ШАГ 2. Только если в названии ничего нет, ищем по описанию.
        # Для нескольких слов требуем совпадение темы, а не одно случайное слово.
        text_conditions = []
        text_params = []

        for term in terms[:5]:
            like = f"%{term}%"
            text_conditions.append(
                """
                (
                    s.description_text ILIKE %s
                    OR s.documents_text ILIKE %s
                    OR s.service_result_text ILIKE %s
                )
                """
            )
            text_params.extend([like, like, like])

        fallback_rows = conn.execute(
            f"""
            SELECT
                s.id,
                s.service_title_text,
                s.description_text,
                s.documents_text,
                s.payment_info_text,
                s.time_term_text,
                s.service_result_text,
                s.reject_reasons_text
            FROM services s
            WHERE {real_service_filter}
              AND ({" OR ".join(text_conditions)})
            ORDER BY
                CASE
                    WHEN s.description_text ILIKE %s THEN 0
                    WHEN s.service_result_text ILIKE %s THEN 1
                    ELSE 2
                END,
                length(s.service_title_text),
                s.service_title_text
            LIMIT %s
            """,
            [
                *text_params,
                f"%{terms[0]}%",
                f"%{terms[0]}%",
                limit,
            ],
        ).fetchall()

        print(f"SEARCH FALLBACK: {terms} -> {len(fallback_rows)}")
        return fallback_rows


def build_context(rows):
    parts = []
    for row in rows:
        parts.append(
            "\n".join(
                [
                    f"Название услуги: {row['service_title_text']}",
                    f"Описание: {clean_html(row.get('description_text')) or 'Не указано'}",
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

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100

    limit = min(max(limit, 1), 1000)

    base_where = """
        s.service_title_text IS NOT NULL
        AND NULLIF(BTRIM(s.service_title_text), '') IS NOT NULL
        AND s.service_title_text <> 'SmevRequestService'
        AND (
              NULLIF(BTRIM(COALESCE(s.description_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.documents_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.payment_info_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.payment_info_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.time_term_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.service_result_text, '')), '') IS NOT NULL
           OR NULLIF(BTRIM(COALESCE(s.reject_reasons_text, '')), '') IS NOT NULL
        )
    """

    with get_db() as conn:
        if query:
            rows = conn.execute(
                f"""
                SELECT
                    s.id,
                    s.service_title_text,
                    s.description_text,
                    s.documents_text,
                    s.payment_info_text,
                    s.time_term_text,
                    s.service_result_text,
                    s.reject_reasons_text,
                    s.service_recipients
                FROM services s
                WHERE {base_where}
                  AND s.service_title_text ILIKE %s
                ORDER BY s.service_title_text
                LIMIT %s
                """,
                (f"%{query}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT
                    s.id,
                    s.service_title_text,
                    s.description_text,
                    s.documents_text,
                    s.payment_info_text,
                    s.time_term_text,
                    s.service_result_text,
                    s.reject_reasons_text,
                    s.service_recipients
                FROM services s
                WHERE {base_where}
                ORDER BY s.service_title_text
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

    return jsonify([
        {
            "id": row["id"],
            "name": row["service_title_text"],
            "payment": clean_html(row.get("payment_info_text")),
            "time": clean_html(row.get("time_term_text")),
            "documents": clean_html(row.get("documents_text")),
            "description": clean_html(row.get("description_text")),
            "result": clean_html(row.get("service_result_text")),
            "reject_reasons": clean_html(row.get("reject_reasons_text")),
            "recipients": clean_html(row.get("service_recipients")),
        }
        for row in rows
    ])




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



@app.post("/api/chat/service/<service_id>")
def api_chat_service(service_id):
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                service_title_text,
                description_text,
                documents_text,
                payment_info_text,
                time_term_text,
                service_result_text,
                reject_reasons_text,
                service_recipients
            FROM services
            WHERE id = %s
            """,
            (service_id,),
        ).fetchone()

    if row is None:
        return jsonify({"error": "Услуга не найдена"}), 404

    if (
        row["service_title_text"] == "SmevRequestService"
        and not any(row.get(field) for field in (
            "description_text",
            "documents_text",
            "payment_info_text",
            "time_term_text",
            "service_result_text",
            "reject_reasons_text",
        ))
    ):
        return jsonify({"error": "Техническая запись, не услуга"}), 404

    row = dict(row)

    for field in (
        "service_recipients",
        "documents_text",
        "payment_info_text",
        "time_term_text",
        "service_result_text",
        "description_text",
        "reject_reasons_text",
    ):
        row[field] = clean_html(row.get(field))

    if not question:
        question = (
            "Объясни простыми словами услугу: "
            + (row["service_title_text"] or "")
        )

    try:
        answer = ask_gigachat(question, [row])
        return jsonify({
            "answer": answer,
            "service": row["service_title_text"],
            "source": "postgresql",
        })
    except Exception as exc:
        print("SERVICE GIGACHAT ERROR:", repr(exc))
        return jsonify({
            "error": "Ошибка ИИ",
            "details": str(exc),
        }), 500


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
