from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///../data/mfc.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def seed_database():
    if Service.query.count() == 0:
        services = [
            Service(
                name="Замена паспорта",
                description="Информация о документах и порядке обращения.",
                category="Документы",
            ),
            Service(
                name="Регистрация по месту жительства",
                description="Основная информация о регистрации и необходимых документах.",
                category="Регистрация",
            ),
            Service(
                name="Получение справок",
                description="Сведения о доступных справках и порядке их получения.",
                category="Справки",
            ),
            Service(
                name="Запись на приём",
                description="Информация о способах предварительной записи.",
                category="Обращение",
            ),
            Service(
                name="Сведения об ИНН",
                description="Информация о получении и восстановлении сведений об ИНН.",
                category="Документы",
            ),
            Service(
                name="Сведения о СНИЛС",
                description="Информация об основных действиях со СНИЛС.",
                category="Документы",
            ),
        ]
        db.session.add_all(services)
        db.session.commit()


@app.route("/")
def index():
    services = Service.query.order_by(Service.id).all()
    return render_template("index.html", services=services)


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("message") or "").strip()

    if not text:
        return jsonify({"error": "Пустой запрос"}), 400

    user_message = Message(role="user", text=text)
    db.session.add(user_message)

    # Демо-ответ. Позже здесь подключается реальный AI API.
    answer = (
        "Демонстрационный ответ. Сейчас сообщение уже сохраняется в базе данных. "
        "На следующем этапе этот обработчик будет передавать вопрос в ИИ и возвращать ответ."
    )

    db.session.add(Message(role="assistant", text=answer))
    db.session.commit()

    return jsonify({"answer": answer})


@app.get("/api/services")
def services_api():
    services = Service.query.order_by(Service.id).all()
    return jsonify([
        {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "category": service.category,
        }
        for service in services
    ])


@app.post("/api/reset")
def reset_demo():
    Message.query.delete()
    db.session.commit()
    return jsonify({"ok": True})


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(debug=True)
