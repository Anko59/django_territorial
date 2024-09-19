run:
	docker compose -f docker-compose.yaml up

build:
	docker compose build

migrations:
	docker compose run aiden_app poetry run python manage.py makemigrations

shell:
	docker compose run django_territorial poetry run python manage.py shell
