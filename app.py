from mfc_app import create_app
from mfc_app.db import check_connection

app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )

    app.run(debug=app.config.get("DEBUG", False))
