.PHONY: help install run-local run-docker build test clean

help:
	@echo "Shorts Maker API - команды для разработки"
	@echo ""
	@echo "Доступные команды:"
	@echo "  install      - Установка зависимостей"
	@echo "  run-local    - Запуск локально (без БД)"
	@echo "  run-docker   - Запуск через Docker Compose"
	@echo "  build        - Сборка Docker образа"
	@echo "  test         - Запуск тестов"
	@echo "  clean        - Очистка временных файлов"
	@echo "  logs         - Просмотр логов Docker"
	@echo "  stop         - Остановка всех сервисов"

install:
	@echo "Установка зависимостей..."
	pip install -r requirements.txt

run-local:
	@echo "Запуск локально без БД..."
	cp .env.local .env
	mkdir -p storage/{input,output,temp}
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

run-docker:
	@echo "Запуск через Docker Compose..."
	docker-compose up -d
	@echo "API доступен по адресу: http://localhost:8000"
	@echo "Документация: http://localhost:8000/docs"

build:
	@echo "Сборка Docker образа..."
	docker build -t shorts-maker-api .

test:
	@echo "Запуск тестов..."
	python -m pytest tests/ -v

clean:
	@echo "Очистка временных файлов..."
	rm -rf storage/temp/*
	rm -rf storage/input/*
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name "__pycache__" -delete

logs:
	@echo "Логи Docker сервисов..."
	docker-compose logs -f

stop:
	@echo "Остановка всех сервисов..."
	docker-compose down

restart:
	@echo "Перезапуск сервисов..."
	docker-compose restart

# Команды для разработки
dev-setup:
	@echo "Настройка окружения разработки..."
	python -m venv venv
	@echo "Активируйте виртуальное окружение:"
	@echo "  Windows: venv\\Scripts\\activate"
	@echo "  Linux/Mac: source venv/bin/activate"
	@echo "Затем выполните: make install"

check-deps:
	@echo "Проверка зависимостей..."
	@python --version || echo "Python не найден!"
	@ffmpeg -version >/dev/null 2>&1 && echo "FFmpeg найден" || echo "FFmpeg не найден!"
	@docker --version >/dev/null 2>&1 && echo "Docker найден" || echo "Docker не найден"

# Команды для продакшена
prod-deploy:
	@echo "Развертывание в продакшене..."
	cp .env .env.backup
	docker-compose -f docker-compose.yml up -d
	@echo "Приложение развернуто"

prod-logs:
	docker-compose -f docker-compose.yml logs -f shorts-maker-api

prod-stop:
	docker-compose -f docker-compose.yml down