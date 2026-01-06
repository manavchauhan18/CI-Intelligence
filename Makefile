.PHONY: help install dev up down logs test clean migrate

help:
	@echo "CI Intelligence Platform - Development Commands"
	@echo ""
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Run in development mode"
	@echo "  make up          - Start all services with Docker Compose"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make test        - Run tests"
	@echo "  make migrate     - Run database migrations"
	@echo "  make clean       - Clean up containers and volumes"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	@echo "Starting services in development mode..."
	@trap 'kill 0' SIGINT; \
	python gateway/main.py & \
	python orchestrator/main.py & \
	python agents/diff_agent/main.py & \
	python agents/intent_agent/main.py & \
	python agents/security_agent/main.py & \
	python agents/performance_agent/main.py & \
	python agents/test_agent/main.py & \
	python agents/arbiter_agent/main.py & \
	wait

up:
	docker-compose up -d
	@echo "Services started. Check status with: docker-compose ps"
	@echo "API Gateway: http://localhost:8000"

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	pytest tests/ -v

migrate:
	alembic upgrade head

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
