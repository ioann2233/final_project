Не могу делать pull requests... (много версий проекта, поэтому проще создавать с 0 репо).
Инструкция по запуску:
1. Клонируем repo.
2. Заходим в директорию
3. поднимаем контейнер (docker compose up --build -d --scale ml_worker=3)
4. Заполняем демкой базу (docker compose exec api python seed.py)
5. Через терминал тестим curl http://localhost:8080/health (на живучесть)
                        curl http://localhost:8080/api/models
6. Личный кабинет (Streamlit → REST API): http://localhost/  или  http://localhost:8502
   REST API docs: http://localhost:8080/api/docs
   Демо: demo_user / demo1234 · админ: demo_admin / admin1234
