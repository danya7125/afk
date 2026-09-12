from mfc_app import create_app
from mfc_app.db import check_connection

app = create_app()


if __name__ == "__main__":
    with app.app_context():
        check_connection()
        print("PostgreSQL: подключение успешно")

    app.run(debug=app.config.get("DEBUG", False))
