Не могу делать pull requests... (много версий проекта, поэтому проще создавать с 0 репо).
Инструкция по запуску: 1. Клонируем repo.
2. Заходим в директорию
3. поднимаем контейнер (docker compose up --build -d --scale ml_worker=3)
4. Заполняем демкой базу (docker compose exec api python seed.py)
5. Через терминал тестим curl http://localhost:8080/health (на живучесть)
                        curl http://localhost:8080/api/models
