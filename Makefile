run:
	docker compose -f docker-compose.yaml up

build:
	docker compose build

migrations:
	docker compose run aiden_app poetry run python manage.py makemigrations
