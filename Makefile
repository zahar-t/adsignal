.PHONY: help install up down bootstrap seed etl api dashboard dagster verify lint typecheck test clean ci-local

help:
	@echo "AdSignal — Competitive Ad Intelligence Platform"
	@echo ""
	@echo "Setup:"
	@echo "  make install      Install Python dependencies"
	@echo "  make up           Start Docker services (MinIO, MongoDB, Lakekeeper, Postgres)"
	@echo "  make down         Stop Docker services"
	@echo "  make bootstrap    Create Iceberg namespace and tables"
	@echo "  make seed         Seed MongoDB with synthetic data"
	@echo ""
	@echo "Pipeline:"
	@echo "  make etl          Run PySpark ETL (MongoDB -> Iceberg)"
	@echo "  make dagster      Launch Dagster UI (http://localhost:3000)"
	@echo ""
	@echo "Serving:"
	@echo "  make api          Start FastAPI server (http://localhost:8000)"
	@echo "  make dashboard    Launch Streamlit dashboard (http://localhost:8501)"
	@echo ""
	@echo "Quality:"
	@echo "  make verify       Run all checks (java, lint, tests)"
	@echo "  make lint         Run ruff linter"
	@echo "  make typecheck    Run mypy"
	@echo "  make test         Run pytest"
	@echo "  make ci-local     Mirror GitHub Actions CI checks locally"

install:
	@echo "Checking Python version..."
	python --version
	pip install -e ".[dev]"

up:
	docker compose -f docker/docker-compose.yml up -d
	@echo "Waiting for services to be healthy..."
	sleep 15
	@echo "✓ Services started"
	@echo "  MinIO console:  http://localhost:9001  (minioadmin / minioadmin)"
	@echo "  Lakekeeper:     http://localhost:8181"
	@echo "  MongoDB:        localhost:27017"

down:
	docker compose -f docker/docker-compose.yml down

bootstrap:
	bash scripts/check_java.sh
	python scripts/bootstrap_iceberg.py

seed:
	python scripts/seed_mongo.py --brands nike adidas apple samsung coca-cola --weeks 16 --ads-per-week 60

etl:
	python scripts/run_etl.py

dagster:
	DAGSTER_HOME=.dagster dagster dev -f adsignal/definitions.py

ci-local:
	@echo "Running CI checks locally (mirrors GitHub Actions)..."
	ruff check adsignal/ api/ dashboard/ tests/
	mypy adsignal/ api/ --ignore-missing-imports
	pytest tests/ -v --tb=short
	@echo "✓ All CI checks passed"

api:
	uvicorn api.main:app --reload --port 8000

dashboard:
	streamlit run dashboard/app.py --server.port 8501

verify: lint typecheck test
	@bash scripts/check_java.sh
	@echo "✓ All checks passed"

lint:
	ruff check adsignal/ api/ dashboard/ tests/

typecheck:
	mypy adsignal/ api/ --ignore-missing-imports

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf dist/ *.egg-info/ .dagster/ tmp/
