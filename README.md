# Первоначальная настройка проекта МФЦ

Веб-приложение для поиска информации о услугах для сотрудников.

## Техно-стек

* **Backend:** Python 3.12, Flask
* **База данных:** PostgreSQL
* **ИИ-ассистент:** GigaChat API
* **Контейнеризация:** Docker, Docker Compose
* **Frontend:** HTML, CSS, JavaScript

## Требования

Для запуска проекта необходимо установить:

* Git
* Docker
* Docker Compose

При запуске проекта через Docker отдельно устанавливать Python и PostgreSQL не требуется.

---

## 1. Клонирование репозитория

Клонируйте репозиторий проекта:

```bash
git clone https://github.com/danya7125/afk
cd afk
```

---

## 2. Создание `.env`

Файл `.env` содержит настройки приложения, параметры подключения к PostgreSQL и данные для работы с GigaChat API.

В проекте присутствует `.env.example`, создайте на его основе `.env`:

### Linux / macOS

```bash
cp .env.example .env
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

После этого откройте `.env` и заполните необходимые значения.

Пример:

```env
PG_HOST=db
PG_PORT=5432
PG_DATABASE=mfc_data
PG_USER=postgres
PG_PASSWORD=your_password

GIGACHAT_CREDENTIALS=your_gigachat_credentials
```

### Переменные окружения

| Переменная               | Назначение                                                                       |
| ------------------------ | -------------------------------------------------------------------------------- |
| **PG_HOST**              | Адрес PostgreSQL. При запуске через Docker Compose используется имя сервиса `db` |
| **PG_PORT**              | Внутренний порт PostgreSQL, по умолчанию `5432`                                  |
| **PG_DATABASE**          | Название базы данных                                                             |
| **PG_USER**              | Пользователь PostgreSQL                                                          |
| **PG_PASSWORD**          | Пароль пользователя PostgreSQL                                                   |
| **GIGACHAT_CREDENTIALS** | Данные авторизации для использования GigaChat API                                |

> **Важно:** при запуске всего проекта через Docker в `PG_HOST` необходимо использовать `db`, а не `localhost`, поскольку backend и PostgreSQL находятся в разных контейнерах.

---

## 3. Сборка и запуск Docker

Проект использует Docker Compose для одновременного запуска backend-приложения и PostgreSQL.

Находясь в корневой папке проекта, выполните:

```bash
docker compose up -d --build
```

Параметр `--build` собирает образ backend-приложения, а `-d` запускает контейнеры в фоновом режиме.

Проверить состояние контейнеров можно командой:

```bash
docker compose ps
```

После успешного запуска должны работать контейнеры:

```text
mfc_backend
mfc_postgres
```

---

## 4. Инициализация PostgreSQL

PostgreSQL запускается автоматически внутри Docker-контейнера.

При первом запуске проекта создаётся база:

```text
mfc_data
```

Начальные данные восстанавливаются из дампа базы данных:

```text
docker/db/mfc_data.dump
```

Скрипт первоначального восстановления:

```text
docker/db/01-restore.sh
```

Запускается автоматически при первой инициализации PostgreSQL.

Проверить наличие базы можно командой:

```bash
docker exec -it mfc_postgres psql -U postgres -l
```

Проверить таблицы:

```bash
docker exec -it mfc_postgres psql -U postgres -d mfc_data -c "\dt"
```

Например, проверить количество услуг:

```bash
docker exec -it mfc_postgres psql -U postgres -d mfc_data -c "SELECT COUNT(*) FROM services;"
```

---

## 5. Работа с данными PostgreSQL

Данные PostgreSQL хранятся в Docker Volume.

Поэтому при обычной остановке проекта:

```bash
docker compose down
```

данные базы **не удаляются**.

После повторного запуска:

```bash
docker compose up -d
```

PostgreSQL продолжит использовать ранее сохранённые данные.

Также можно просто остановить контейнеры:

```bash
docker compose stop
```

и снова запустить:

```bash
docker compose start
```

> **Внимание:** команда

```bash
docker compose down -v
```

удаляет Docker Volume PostgreSQL.

В этом случае сохранённые данные базы будут удалены, а при следующем запуске PostgreSQL создаст базу заново и выполнит первоначальную инициализацию из `mfc_data.dump`.

---

## 6. Запуск приложения

При использовании Docker Compose отдельно запускать Flask не требуется.

Backend запускается автоматически внутри контейнера:

```text
mfc_backend
```

После запуска Docker приложение доступно в браузере по адресу:

```text
http://localhost:5000
```

---

## 7. Просмотр логов

Посмотреть логи всего проекта:

```bash
docker compose logs
```

Следить за логами в реальном времени:

```bash
docker compose logs -f
```

Логи backend:

```bash
docker compose logs web --tail=100
```

Логи PostgreSQL:

```bash
docker compose logs db --tail=100
```

Это может быть полезно при диагностике ошибок подключения к PostgreSQL или GigaChat API.

---

## 8. GigaChat API

Для работы ИИ-ассистента необходимо указать действительные данные авторизации GigaChat в `.env`:

```env
GIGACHAT_CREDENTIALS=your_gigachat_credentials
```

Backend использует GigaChat API для формирования ответов пользователю на основе информации об услугах.

Если GigaChat недоступен или возникает ошибка соединения, основная база данных и каталог услуг могут продолжать работать, однако функции ИИ-ассистента могут быть временно недоступны.

---

## 9. Остановка проекта

Для обычной остановки:

```bash
docker compose down
```

Для последующего запуска:

```bash
docker compose up -d
```

Если код проекта или Dockerfile был изменён:

```bash
docker compose up -d --build
```

---

Таким образом, для стандартного запуска проекта достаточно:

```bash
docker compose up -d --build
```

После чего открыть:

```text
http://localhost:5000
```
