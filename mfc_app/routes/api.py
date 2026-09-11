import logging

from flask import Blueprint, current_app, jsonify, request

from ..catalog import CATEGORIES
from ..repositories.services import ServiceRepository
from ..services.ai import AiAssistantService

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


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
    rows = repository.list(
        query=query,
        category=category,
        status=status,
        limit=limit,
    )
    return jsonify([service.to_summary_dict() for service in rows])


@api_bp.get("/services/<service_id>")
def service_details(service_id: str):
    service = ServiceRepository().get_by_id(service_id)
    if not service:
        return jsonify({"error": "Услуга не найдена"}), 404
    return jsonify(service.to_dict())


@api_bp.post("/chat/service/<service_id>")
def chat_service(service_id: str):
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()

    if not question:
        question = "Объясни эту услугу простыми словами."

    max_chars = current_app.config["CHAT_MAX_INPUT_CHARS"]
    if len(question) > max_chars:
        return jsonify({
            "error": f"Запрос слишком длинный. Максимум {max_chars} символов."
        }), 400

    try:
        answer, service = AiAssistantService().answer_for_service(
            question,
            service_id,
        )
        return jsonify({
            "answer": answer,
            "service": service.to_summary_dict(),
            "source": "postgresql",
        })
    except LookupError:
        return jsonify({"error": "Услуга не найдена"}), 404
    except Exception:
        logger.exception("Ошибка при объяснении конкретной услуги")
        return jsonify({
            "error": "Не удалось получить ответ ИИ. Проверьте настройки сервиса и повторите запрос."
        }), 500


@api_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()

    if not question:
        return jsonify({"error": "Пустой запрос"}), 400

    max_chars = current_app.config["CHAT_MAX_INPUT_CHARS"]
    if len(question) > max_chars:
        return jsonify({"error": f"Запрос слишком длинный. Максимум {max_chars} символов."}), 400

    try:
        answer, matches = AiAssistantService().answer(question)
        return jsonify({
            "answer": answer,
            "matched": [{"id": item.id, "name": item.name} for item in matches],
            "source": "postgresql",
        })
    except Exception:
        logger.exception("Ошибка при обработке запроса ИИ")
        return jsonify({"error": "Не удалось получить ответ ИИ. Проверьте настройки сервиса и повторите запрос."}), 500
