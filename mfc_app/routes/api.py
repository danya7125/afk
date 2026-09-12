import logging
import uuid

import os
import psycopg

from flask import Blueprint, current_app, jsonify, request, make_response

from ..catalog import CATEGORIES, CATEGORY_NAMES, detect_service_category
from ..repositories.chat_history import ChatHistoryRepository
from ..repositories.services import ServiceRepository
from ..services.ai import AiAssistantService

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)
chat_history = ChatHistoryRepository()


def _session_id() -> str:
    value = (request.headers.get("X-MFC-Session-ID") or "").strip()
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        return str(uuid.uuid4())


def _finish_response(payload: dict, session_id: str):
    response = make_response(jsonify(payload))
    response.headers["X-MFC-Session-ID"] = session_id
    return response


def _conversation_context(session_id: str, limit: int = 6) -> str:
    try:
        rows = chat_history.list_for_session(session_id, limit=limit)
    except Exception:
        logger.exception("Не удалось получить контекст истории чата")
        return ""

    parts = []
    for row in rows[-limit:]:
        user_message = str(row.get("user_message") or "").strip()
        ai_response = str(row.get("ai_response") or "").strip()
        if user_message:
            parts.append(f"Пользователь: {user_message}")
        if ai_response:
            parts.append(f"Ассистент: {ai_response}")
    return "\n".join(parts)


@api_bp.get("/categories")
def categories():
    return jsonify(CATEGORIES)


@api_bp.get("/services")
def services():
    query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    status = (request.args.get("status") or "").strip()

    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(limit, 1), 500)

    repository = ServiceRepository()
    rows = repository.list(query=query, category=category, status=status, limit=limit)
    return jsonify([service.to_summary_dict() for service in rows])


@api_bp.get("/services/<service_id>")
def service_details(service_id: str):
    service = ServiceRepository().get_by_id(service_id)
    if not service:
        return jsonify({"error": "Услуга не найдена"}), 404
    return jsonify(service.to_dict())


@api_bp.get("/chat/history")
def chat_history_list():
    session_id = _session_id()
    category_id = (request.args.get("category") or "").strip()

    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(limit, 1), 200)

    rows = chat_history.list_for_session(session_id, category_id=category_id, limit=limit)
    return _finish_response({"session_id": session_id, "items": rows}, session_id)


@api_bp.delete("/chat/history")
def chat_history_clear():
    session_id = _session_id()
    category_id = (request.args.get("category") or "").strip()
    chat_history.clear_session(session_id, category_id=category_id)
    return _finish_response({"ok": True, "session_id": session_id}, session_id)


@api_bp.post("/chat/service/<service_id>")
def chat_service(service_id: str):
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()
    requested_category = (payload.get("category") or "").strip()
    session_id = _session_id()

    if not question:
        question = "Объясни эту услугу простыми словами."

    max_chars = current_app.config["CHAT_MAX_INPUT_CHARS"]
    if len(question) > max_chars:
        return _finish_response({
            "error": f"Запрос слишком длинный. Максимум {max_chars} символов."
        }, session_id), 400

    try:
        answer, service = AiAssistantService().answer_for_service(question, service_id)
        category_id = requested_category or detect_service_category(service)
        category_name = CATEGORY_NAMES.get(category_id, CATEGORY_NAMES["other"])

        history_id = chat_history.add(
            session_id=session_id,
            category_id=category_id,
            category_name=category_name,
            service_id=service.id,
            service_name=service.name,
            user_message=question,
            ai_response=answer,
            matched_services=[{"id": service.id, "name": service.name}],
        )
        logger.info("CHAT SAVED id=%s session=%s category=%s service=%s", history_id, session_id, category_name, service.id)

        return _finish_response({
            "answer": answer,
            "service": service.to_summary_dict(),
            "source": "postgresql",
            "session_id": session_id,
            "category": {"id": category_id, "name": category_name},
            "history_id": history_id,
        }, session_id)
    except LookupError:
        return _finish_response({"error": "Услуга не найдена"}, session_id), 404
    except Exception:
        logger.exception("Ошибка при объяснении конкретной услуги")
        return _finish_response({
            "error": "Не удалось получить ответ ИИ. Проверьте настройки сервиса и повторите запрос."
        }, session_id), 500


@api_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()
    requested_category = (payload.get("category") or "").strip()
    session_id = _session_id()

    if not question:
        return _finish_response({"error": "Пустой запрос"}, session_id), 400

    max_chars = current_app.config["CHAT_MAX_INPUT_CHARS"]
    if len(question) > max_chars:
        return _finish_response({
            "error": f"Запрос слишком длинный. Максимум {max_chars} символов."
        }, session_id), 400

    try:
        decision, matches = AiAssistantService().answer(
            question,
            conversation_context=_conversation_context(session_id),
        )
        matched = [{"id": item.id, "name": item.name} for item in matches]
        answer = decision.get("answer") or decision.get("question") or ""

        if requested_category:
            category_id = requested_category
        elif matches:
            category_id = detect_service_category(matches[0])
        else:
            category_id = "other"

        category_name = CATEGORY_NAMES.get(category_id, CATEGORY_NAMES["other"])

        history_id = chat_history.add(
            session_id=session_id,
            category_id=category_id,
            category_name=category_name,
            service_id=matches[0].id if matches else None,
            service_name=matches[0].name if matches else None,
            user_message=question,
            ai_response=answer,
            matched_services=matched,
        )
        logger.info("CHAT SAVED id=%s session=%s category=%s service=%s", history_id, session_id, category_name, matches[0].id if matches else None)

        return _finish_response({
            "answer": answer,
            "type": decision.get("type", "answer"),
            "question": decision.get("question", ""),
            "options": decision.get("options", []),
            "matched": matched,
            "source": "postgresql",
            "session_id": session_id,
            "category": {"id": category_id, "name": category_name},
            "history_id": history_id,
        }, session_id)
    except Exception:
        logger.exception("Ошибка при обработке запроса ИИ")
        return _finish_response({
            "error": "Не удалось получить ответ ИИ. Проверьте настройки сервиса и повторите запрос."
        }, session_id), 500

@api_bp.get("/recent_updates")
def recent_updates():
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = os.getenv("PG_PORT", "5432")
    PG_DATABASE = os.getenv("PG_DATABASE", "mfc_data")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD")

    try:
        with psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE, 
            user=PG_USER, password=PG_PASSWORD
        ) as conn:
            
           result = conn.execute("""
                SELECT id, service_title_text 
                FROM services 
                WHERE xmin::text::bigint = (
                    SELECT MAX(xmin::text::bigint) FROM services
                )
            """).fetchall()

           updates = [{"id": row[0], "title": row[1]} for row in result]
            
        return jsonify(updates)
    except Exception as e:
        logger.exception("Ошибка при получении последних обновлений")
        return jsonify({"error": str(e)}), 500