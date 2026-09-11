from flask import Flask, render_template, request, jsonify, abort

import psycopg2
from psycopg2.extras import RealDictCursor

from dotenv import load_dotenv

import os
import re
import html


app = Flask(__name__)

load_dotenv()


PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "mfc_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD")


def get_db():
    if not PG_PASSWORD:
        raise RuntimeError(
            "Переменная PG_PASSWORD не найдена в файле .env"
        )

    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)

    return text.strip()

@app.route("/")
def index():
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT id, group_key, name
                FROM classification_groups
                ORDER BY id
            """)
            groups = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM services
            """)
            services_count = cursor.fetchone()["c"]

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM classification_categories
            """)
            categories_count = cursor.fetchone()["c"]

    finally:
        conn.close()

    return render_template(
        "index.html",
        groups=groups,
        services_count=services_count,
        categories_count=categories_count,
    )


@app.get("/api/categories")
def api_categories():
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
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
            """)

            rows = cursor.fetchall()

    finally:
        conn.close()

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
            groups[key]["categories"].append({
                "id": row["category_id"],
                "source_id": row["source_id"],
                "name": row["category_name"],
            })

    return jsonify(list(groups.values()))


@app.get("/api/services")
def api_services():
    query = (request.args.get("q") or "").strip()

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    limit = min(max(limit, 1), 100)

    conn = get_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:

            if query:
                cursor.execute("""
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
                """, (f"%{query}%", limit))

            else:
                cursor.execute("""
                    SELECT
                        id,
                        service_title_text,
                        payment_info_text,
                        time_term_text,
                        documents_text
                    FROM services
                    ORDER BY service_title_text
                    LIMIT %s
                """, (limit,))

            rows = cursor.fetchall()

    finally:
        conn.close()

    return jsonify([
        {
            "id": row["id"],
            "name": row["service_title_text"],
            "payment": clean_html(row["payment_info_text"]),
            "time": clean_html(row["time_term_text"]),
            "documents": clean_html(row["documents_text"]),
        }
        for row in rows
    ])


@app.get("/api/services/<service_id>")
def api_service(service_id):
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:

            cursor.execute("""
                SELECT *
                FROM services
                WHERE id = %s
            """, (service_id,))

            row = cursor.fetchone()

            if row is None:
                abort(404)

            cursor.execute("""
                SELECT
                    classification_group,
                    classification_category_id
                FROM service_classification_refs
                WHERE source_service_ref = %s
                LIMIT 50
            """, (service_id,))

            refs = cursor.fetchall()

    finally:
        conn.close()

    service = dict(row)

    service["service_recipients"] = clean_html(
        service["service_recipients"]
    )

    service["documents_text"] = clean_html(
        service["documents_text"]
    )

    service["payment_info_text"] = clean_html(
        service["payment_info_text"]
    )

    service["time_term_text"] = clean_html(
        service["time_term_text"]
    )

    service["service_result_text"] = clean_html(
        service["service_result_text"]
    )

    service["description_text"] = clean_html(
        service["description_text"]
    )

    service["reject_reasons_text"] = clean_html(
        service["reject_reasons_text"]
    )

    service["classification_refs"] = [
        dict(x) for x in refs
    ]

    return jsonify(service)


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}

    message = (payload.get("message") or "").strip()

    if not message:
        return jsonify({
            "error": "Пустой запрос"
        }), 400

    conn = get_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:

            cursor.execute("""
                SELECT
                    id,
                    service_title_text,
                    documents_text,
                    payment_info_text,
                    time_term_text,
                    service_result_text
                FROM services
                WHERE service_title_text ILIKE %s
                ORDER BY service_title_text
                LIMIT 5
            """, (f"%{message}%",))

            rows = cursor.fetchall()

            if not rows:
                words = [
                    w
                    for w in re.findall(
                        r"[А-Яа-яЁёA-Za-z0-9]+",
                        message.lower()
                    )
                    if len(w) >= 4
                ]

                if words:
                    conditions = []
                    params = []

                    for word in words[:6]:
                        conditions.append(
                            "service_title_text ILIKE %s"
                        )
                        params.append(f"%{word}%")

                    where = " OR ".join(conditions)

                    cursor.execute(f"""
                        SELECT
                            id,
                            service_title_text,
                            documents_text,
                            payment_info_text,
                            time_term_text,
                            service_result_text
                        FROM services
                        WHERE {where}
                        ORDER BY service_title_text
                        LIMIT 5
                    """, params)

                    rows = cursor.fetchall()

    finally:
        conn.close()

    if rows:
        best = rows[0]

        answer = (
            f"По вашему запросу найдена услуга: "
            f"«{best['service_title_text']}».\n\n"
            f"Документы: "
            f"{clean_html(best['documents_text']) or 'данные не указаны'}\n"
            f"Оплата: "
            f"{clean_html(best['payment_info_text']) or 'данные не указаны'}\n"
            f"Срок: "
            f"{clean_html(best['time_term_text']) or 'данные не указаны'}"
        )

    else:
        answer = (
            "В базе данных не нашлась услуга с таким названием. "
            "На следующем этапе сюда подключим ИИ, который будет "
            "искать нужную услугу по смыслу вопроса и формировать "
            "ответ на основе данных БД."
        )

    return jsonify({
        "answer": answer,
        "matched": [
            r["service_title_text"]
            for r in rows
        ]
    })


if __name__ == "__main__":
    app.run(debug=True)