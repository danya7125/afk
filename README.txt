# МФЦ Flask + PostgreSQL + GigaChat

## 1. Установка

python -m pip install -r requirements.txt

## 2. PostgreSQL

Нужно создать базу:

CREATE DATABASE mfc_data;

Затем восстановить командный dump:

PowerShell:
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -U postgres -h 127.0.0.1 -p 5432 -d mfc_data mfc_data.dump

Если PostgreSQL установлен в другой папке, используйте путь к своему pg_restore.exe.

## 3. .env

Создайте в корне проекта файл `.env`:

PG_HOST=127.0.0.1
PG_PORT=5432
PG_DATABASE=mfc_data
PG_USER=postgres
PG_PASSWORD=ваш_пароль

GIGACHAT_CREDENTIALS=ваш_authorization_key
GIGACHAT_SCOPE=GIGACHAT_API_PERS

Не добавляйте `.env` в GitHub.

## 4. Запуск

python app.py

Если PostgreSQL подключился, в терминале появится:
PostgreSQL: подключение успешно

После этого:
http://127.0.0.1:5000

## Что изменилось

SQLite больше не используется.
Flask напрямую подключается к PostgreSQL.
Поиск услуг и категорий идёт из PostgreSQL.
GigaChat получает найденные данные из PostgreSQL и формирует ответ.

Для другого участника:
1. git clone
2. pip install -r requirements.txt
3. создать PostgreSQL database mfc_data
4. pg_restore mfc_data.dump
5. создать свой .env
6. python app.py
