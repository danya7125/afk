# МФЦ: Flask + PostgreSQL + GigaChat

Проект разделён на слои, чтобы UI, SQL и ИИ-логика не находились в одном app.py.

## Структура

app.py                         — только запуск приложения
mfc_app/__init__.py            — Flask application factory
mfc_app/config.py              — конфигурация из .env
mfc_app/db.py                  — подключение к PostgreSQL
mfc_app/models.py              — модель Service
mfc_app/catalog.py             — категории интерфейса
mfc_app/routes/web.py          — HTML-страницы
mfc_app/routes/api.py          — JSON API
mfc_app/repositories/services.py — SQL и чтение services
mfc_app/services/search.py     — нормализация/поиск терминов
mfc_app/services/ai.py         — RAG-контекст + GigaChat
mfc_app/utils/text.py          — очистка HTML из БД
static/app.js                  — frontend-логика
static/style.css               — стили
templates/index.html           — HTML-шаблон
mfc_data.dump                  — PostgreSQL dump

## Важное изменение

Карточки услуг и кнопка «Открыть» больше НЕ используют ИИ.

- список услуг получает description_text прямо из PostgreSQL;
- /api/services отдаёт только id, name и description;
- /api/services/<id> отдаёт полные данные выбранной услуги из PostgreSQL;
- GigaChat используется только в отдельном ИИ-помощнике /api/chat.

## 1. Установка

python -m pip install -r requirements.txt

## 2. PostgreSQL

Создайте базу:

CREATE DATABASE mfc_data;

Восстановите dump (пример для Windows / PowerShell):

& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -U postgres -h 127.0.0.1 -p 5432 -d mfc_data mfc_data.dump

Если PostgreSQL установлен в другой папке, укажите свой путь к pg_restore.exe.

## 3. .env

Скопируйте .env.example в .env и заполните минимум:

PG_PASSWORD=ваш_пароль
GIGACHAT_CREDENTIALS=ваш_authorization_key

.env не коммитьте в Git.

## 4. Запуск

python app.py

После успешной проверки PostgreSQL:

PostgreSQL: подключение успешно

Откройте:
http://127.0.0.1:5000

## Что исправлено

- app.py разбит на маршруты, сервисы, репозиторий, модель и DB/config;
- убран ИИ из обычного просмотра услуг;
- description карточки берётся из services.description_text;
- полная услуга загружается из PostgreSQL только при открытии карточки;
- category/status фильтры теперь реально обрабатываются backend-ом;
- поиск ИИ отделён от SQL и ранжирует кандидатов до вызова LLM;
- если подходящая услуга не найдена, LLM вообще не вызывается;
- system prompt отделён от user prompt;
- ошибки сервера больше не отправляют внутренний exception пользователю;
- добавлен лимит длины сообщения;
- JavaScript вынесен из index.html в static/app.js;
- убраны дубли templates/templates и templates/static.

## Следующий production-этап

Для публичного сервиса стоит добавить connection pool, миграции (Alembic), rate limiting, auth/roles,
логирование/метрики, тесты API, PostgreSQL full-text search/pg_trgm или embeddings + pgvector,
а категории услуг хранить в БД явно, а не определять ключевыми словами.
