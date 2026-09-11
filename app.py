from flask import Flask, render_template, request, jsonify, abort
from pathlib import Path
import sqlite3
import re
import html

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "mfc_data.db"

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    groups = conn.execute(
        "SELECT id, group_key, name FROM classification_groups ORDER BY id"
    ).fetchall()
    services_count = conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
    categories_count = conn.execute(
        "SELECT COUNT(*) AS c FROM classification_categories"
    ).fetchone()["c"]
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
    rows = conn.execute("""
        SELECT cg.id AS group_id,
               cg.name AS group_name,
               cc.id AS category_id,
               cc.source_id,
               cc.name AS category_name
        FROM classification_groups cg
        LEFT JOIN classification_categories cc ON cc.group_id = cg.id
        ORDER BY cg.id, cc.name
    """).fetchall()
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
    limit = min(max(int(request.args.get("limit", 50)), 1), 100)

    conn = get_db()

    if query:
        rows = conn.execute("""
            SELECT id, service_title_text, payment_info_text,
                   time_term_text, documents_text
            FROM services
            WHERE service_title_text LIKE ?
            ORDER BY service_title_text
            LIMIT ?
        """, (f"%{query}%", limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, service_title_text, payment_info_text,
                   time_term_text, documents_text
            FROM services
            ORDER BY service_title_text
            LIMIT ?
        """, (limit,)).fetchall()

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
    row = conn.execute("""
        SELECT *
        FROM services
        WHERE id = ?
    """, (service_id,)).fetchone()

    if row is None:
        conn.close()
        abort(404)

    refs = conn.execute("""
        SELECT classification_group,
               classification_category_id
        FROM service_classification_refs
        WHERE source_service_ref = ?
        LIMIT 50
    """, (service_id,)).fetchall()
    conn.close()

    service = dict(row)
    service["service_recipients"] = clean_html(service["service_recipients"])
    service["documents_text"] = clean_html(service["documents_text"])
    service["payment_info_text"] = clean_html(service["payment_info_text"])
    service["time_term_text"] = clean_html(service["time_term_text"])
    service["service_result_text"] = clean_html(service["service_result_text"])
    service["description_text"] = clean_html(service["description_text"])
    service["reject_reasons_text"] = clean_html(service["reject_reasons_text"])
    service["classification_refs"] = [dict(x) for x in refs]
    return jsonify(service)


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Пустой запрос"}), 400

    conn = get_db()
    rows = conn.execute("""
        SELECT id, service_title_text, documents_text,
               payment_info_text, time_term_text, service_result_text
        FROM services
        WHERE service_title_text LIKE ?
        ORDER BY service_title_text
        LIMIT 5
    """, (f"%{message}%",)).fetchall()

    # A small heuristic search for the MVP before the AI is connected.
    if not rows:
        words = [w for w in re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", message.lower()) if len(w) >= 4]
        score_parts = []
        for word in words[:6]:
            score_parts.append(f"service_title_text LIKE '%{word}%'")
        if score_parts:
            where = " OR ".join(score_parts)
            params = [f"%{word}%" for word in words[:6]]
            rows = conn.execute(f"""
                SELECT id, service_title_text, documents_text,
                       payment_info_text, time_term_text, service_result_text
                FROM services
                WHERE {where}
                LIMIT 5
            """, params).fetchall()

    conn.close()

    if rows:
        best = rows[0]
        answer = (
            f"По вашему запросу найдена услуга: «{best['service_title_text']}».\n\n"
            f"Документы: {clean_html(best['documents_text']) or 'данные не указаны'}\n"
            f"Оплата: {clean_html(best['payment_info_text']) or 'данные не указаны'}\n"
            f"Срок: {clean_html(best['time_term_text']) or 'данные не указаны'}"
        )
    else:
        answer = (
            "В базе данных не нашлась услуга с таким названием. "
            "На следующем этапе сюда подключим ИИ, который будет искать нужную услугу "
            "по смыслу вопроса и формировать ответ на основе данных БД."
        )

    return jsonify({"answer": answer, "matched": [r["service_title_text"] for r in rows]})


if __name__ == "__main__":
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Не найдена база данных: {DB_PATH}")
    app.run(debug=True)
