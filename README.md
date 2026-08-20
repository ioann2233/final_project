# ML Service — кабинет СКУД

Сервис для курса: регистрация, баланс в условных кредитах, детекция людей/машин по кадру с камеры и список «своих».

По сути это три куска, которые крутятся вместе:

1. **FastAPI** — REST API
2. **Streamlit** — личный кабинет
3. **воркеры + RabbitMQ** — очередь для ML-задач

Детекция на вкладке «Камера» считается сразу в API и сразу списывает кредиты. Старый путь через очередь (`POST /api/predictions/`) тоже жив, просто из UI его убрали.

## Что нужно

- Docker Desktop
- файл `app/.env` (уже лежит в репе)

Локально Python ставить не обязательно — всё в контейнерах.

## Запуск

Из корня репозитория:

```powershell
docker compose up --build -d --scale ml_worker=3
```

Первый билд долгий. Там torch, ultralytics и скачивание YOLO/лиц. Это нормально, можно отойти минут на 10–15.

Потом закинуть демо-данные:

```powershell
docker compose exec api python seed.py
```

`seed.py` дропает таблицы и создаёт пользователей с моделями заново. Не запускай это на живых данных, если они тебе ещё нужны.

Проверка, что API живой:

```powershell
curl http://localhost:8080/health
```

Остановка:

```powershell
docker compose down
```

Если хочешь ещё и стереть Postgres/RabbitMQ:

```powershell
docker compose down -v
```

После `-v` seed нужно прогнать снова.

## Куда тыкаться

| Что | Адрес |
|---|---|
| Кабинет | http://localhost:8502 |
| То же через nginx | http://localhost |
| API | http://localhost:8080 |
| Swagger | http://localhost:8080/api/docs |
| RabbitMQ UI | http://localhost:15672 (`rmuser` / `rmpassword`) |

Демо-логины:

- пользователь: `demo_user` / `demo1234` (100 ₽)
- админ: `demo_admin` / `admin1234` (1000 ₽)

Если seed гоняли, пока ты был залогинен в Streamlit — лучше выйти и войти заново. Старый JWT будет от старого user id.

## Как этим пользоваться

1. Войти или зарегистрироваться.
2. На вкладке **Свои люди и машины** закинуть фото. Для человека нужно нормальное лицо анфас, иначе SFace не вытащит эмбеддинг.
3. На вкладке **Камера** выбрать модель, сделать снимок, нажать «Детектировать и списать».
4. Зелёная рамка — свой, красная — чужой.
5. Каждый запуск списывает цену модели. Повтор с другой моделью списывает ещё раз.
6. **История** показывает детекции и движение кредитов.

Если баланс меньше цены модели, кнопка не активна. Пополнить можно в личном кабинете (это учебный баланс, эквайринга нет).

## Карта проекта

```
KarpovProject-master/
├── docker-compose.yaml
├── nginx/
├── scripts/
└── app/                  ← весь код сервиса, этот каталог монтируется в контейнеры
    ├── api.py            ← точка входа FastAPI
    ├── main.py           ← Flask app (SQLAlchemy живёт здесь)
    ├── streamlit_app.py  ← кабинет
    ├── seed.py
    ├── models/           ← таблицы
    ├── routes/           ← эндпоинты FastAPI
    ├── schemas/          ← pydantic
    ├── service/          ← бизнес-логика
    ├── worker/           ← консьюмеры очереди
    ├── ui/               ← клиент API + страница камеры
    ├── auth/             ← JWT, формы, пароли
    ├── tests/
    └── uploads/          ← загруженные фото
```

### `app/api.py` и `app/routes/`

Публичный API. Роутеры:

- `/api/users` — регистрация, логин, `/me`
- `/api/balance` — баланс, пополнение, транзакции
- `/api/models` — список моделей и цены
- `/api/predictions` — очередь предиктов + `POST /camera` для снимка
- `/api/known-entities` — «свои» люди и машины

Авторизация через `Authorization: Bearer <jwt>`. Это собирается в `app/deps.py`.

### `app/main.py` и `app/models/`

Flask нужен не как второй веб-сервер, а как обёртка над Flask-SQLAlchemy. FastAPI лезет в БД через `ui/context.py` (`run_with_context`), чтобы не переписывать всё на SQLAlchemy 2.0 session.

Таблицы:

- `users` / `wallets` — аккаунт и баланс
- `transactions` — пополнения и списания
- `ml_models` — YOLO-модели и цена за запуск
- `ml_tasks` + `prediction_results` — задача и её детекции
- `known_entities` — фото и дескриптор «своего»

### `app/service/`

Сюда складывал логику, чтобы роуты не раздувались.

- `service/testing/` — пользователи, кошелёк, задачи, транзакции. Название папки историческое, это не тесты.
- `service/testing/camera_log.py` — запись кадра с камеры в историю **и списание** цены модели.
- `service/detection/` — YOLO + YuNet/SFace. Людей сравниваем по лицу, машины — по простой HSV-гистограмме (это не номер, просто «похоже на ту же тачку»).
- `service/known_entity.py` — загрузка «своих».
- `service/rm/` — публикация `task_id` в RabbitMQ.

### `app/worker/`

`python -m worker.main` слушает очередь. Берёт `task_id`, гоняет YOLO, пишет результат, списывает кредиты только если предикт прошёл. Если упало — статус `failed`, денег не берём (или возвращаем, если уже списали).

В compose воркеров можно скейлить: `--scale ml_worker=3`.

### `app/ui/` и `app/streamlit_app.py`

Кабинет сам в БД не ходит. Только HTTP на API (`ui/api_client.py`).

Страницы: главная, вход, регистрация, кабинет, камера, свои, история, админка.

Камера живёт в `ui/camera_detection.py`. Live WebRTC убрал — Streamlit с ним регулярно ронял фронт. Остался снимок.

### `nginx/`

Прокси на 80/443. `/api/` и `/health` → FastAPI, всё остальное → Streamlit. Для локальной разработки проще открывать `:8502` и `:8080` напрямую.

### `scripts/`

- `run_e2e_scenarios.py` — дергает живой API: регистрация, баланс, предикт, история.
- `generate_coverage_report.py` — прогоняет pytest под coverage и рисует html-отчёт.

## Как идут запросы

**Снимок с камеры (то, что в UI):**

```
Streamlit → POST /api/predictions/camera
         → YOLO + сравнение со «своими»
         → запись MLTask (completed) + Transaction
         → списание с кошелька
```

Очередь тут не участвует.

**Старый ML-запрос через API:**

```
клиент → POST /api/predictions/
       → валидация путей
       → задача в БД со статусом created
       → сообщение в RabbitMQ
воркер → YOLO
       → completed + списание
       → или failed без списания
```

## Тесты

Юнит-тесты крутятся на sqlite in-memory, RabbitMQ мокается. Из папки `app`:

```powershell
python -m pytest tests -q
```

Coverage:

```powershell
python ../scripts/generate_coverage_report.py
```

E2E (нужен уже поднятый compose + seed):

```powershell
python scripts/run_e2e_scenarios.py
```

## Если что-то отвалилось

- **UI не видит API** — смотри, что контейнер `api` healthy: `docker compose ps`. Streamlit ходит на `http://api:8080` внутри сети compose.
- **AttributeError / старый код** — каталог `app/` примонтирован в контейнер. Иногда Streamlit кеширует модуль, тогда `docker compose restart app`.
- **История пустая после seed** — так и должно быть, seed сейчас не создаёт фейковых предиктов.
- **Не хватает средств** — цена модели на главной. YOLOv8n = 10 ₽, YOLOv8s = 25 ₽, Access Control = 40 ₽.
- **Лицо не находится** — другое фото, без сильного поворота и тёмных очков.

Логи:

```powershell
docker compose logs -f api
docker compose logs -f ml_worker
docker compose logs -f app
```
