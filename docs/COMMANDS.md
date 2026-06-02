# OpsPilot: Developer Command Reference

This document serves as a cheat sheet for all essential commands needed to develop, test, and maintain the OpsPilot backend.

> [!NOTE]
> All commands assume you are running them from the root of the project directory.

## 📦 Dependency Management (Poetry)

OpsPilot uses [Poetry](https://python-poetry.org/) for strict dependency management.

| Command | Description |
|---|---|
| `poetry install` | Install all dependencies in a virtual environment. |
| `poetry add <package>` | Add and install a new dependency (adds to `pyproject.toml`). |
| `poetry add --group dev <package>` | Add a dependency only for development (e.g., a testing tool). |
| `poetry remove <package>` | Remove a dependency. |
| `poetry run <command>` | Execute a command within the Poetry virtual environment. |
| `poetry shell` | Spawn a shell within the virtual environment (so you don't need `poetry run`). |
| `poetry update` | Update all dependencies to their latest compatible versions. |

---

## 🚀 Development Server

Commands to start the API and external services.

| Command | Description |
|---|---|
| `docker-compose up -d` | Start background services (PostgreSQL, Redis, Kong). |
| `docker-compose down` | Stop and remove background services. |
| `poetry run uvicorn app.main:app --reload` | Start the FastAPI development server with hot-reloading. |
| `poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker` | Run the application using the production ASGI server. |

---

## 🗄️ Database & Migrations (Alembic)

We use Alembic to manage async SQLAlchemy migrations.

| Command | Description |
|---|---|
| `poetry run alembic revision --autogenerate -m "Message"` | Generate a new migration script based on changes in `models.py`. |
| `poetry run alembic upgrade head` | Apply all pending migrations to the database. |
| `poetry run alembic downgrade -1` | Revert the last applied migration. |
| `poetry run alembic history` | View the chronological history of all migrations. |
| `poetry run alembic current` | View the current migration applied to the database. |

> [!WARNING]
> Always review the auto-generated migration file in the `migrations/versions/` folder before running `alembic upgrade head`, as Alembic cannot perfectly detect all schema changes (e.g., column renaming).

---

## 🧹 Code Quality & Linting

OpsPilot enforces strict code quality using Ruff, Black, MyPy, and Pre-commit.

| Command | Description |
|---|---|
| `poetry run pre-commit install` | Install git hooks to run linters automatically before every commit. |
| `poetry run pre-commit run --all-files` | Manually run all pre-commit hooks against all files. |
| `poetry run ruff check .` | Run the Ruff linter to find syntax, import, and logic errors. |
| `venv\Scripts\ruff check --fix; venv\Scripts\ruff format` | Run the Ruff linter to find syntax, import, and logic errors and automatically fix fixable linting errors. |
| `poetry run ruff check --fix .` | Automatically fix fixable linting errors. |
| `poetry run ruff format .` | Format the entire codebase to comply with standard Python style. |
| `poetry run mypy app/` | Run static type checking across the `app/` directory. |

---

## 🧪 Testing (Pytest)

> [!IMPORTANT]
> The testing environment should ideally point to a separate testing database to prevent data corruption.

| Command | Description |
|---|---|
| `poetry run pytest` | Run the entire test suite. |
| `poetry run pytest tests/path/to/test.py` | Run a specific test file. |
| `poetry run pytest -k "test_name"` | Run a specific test function by name. |
| `poetry run pytest -x` | Stop the test suite immediately after the first failure. |
| `poetry run pytest -s` | Prevent Pytest from capturing stdout (allows `print()` statements to show). |
| `poetry run pytest --cov=app` | Run tests and generate a code coverage report for the `app/` folder. |

---

## ⚙️ Redis & Background Tasks (Future)

Commands for when Celery workers are fully integrated.

| Command | Description |
|---|---|
| `poetry run celery -A app.core.celery_app worker --loglevel=info` | Start a Celery worker to process background jobs. |
| `poetry run celery -A app.core.celery_app beat --loglevel=info` | Start the Celery beat scheduler for periodic tasks. |
| `docker exec -it opspilot-redis redis-cli` | Enter the Redis CLI to inspect cached data and pub/sub queues. |
