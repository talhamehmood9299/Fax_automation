# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI API (`server.py`), LLM pipeline (`process_fax.py`), RAG store (`correction_store_rag.py`), prompts (`ollama_agent.py`). Env at `backend/.env(.example)`.
- `frontend/`: Tkinter client (`client.py`) that drives Selenium, helpers, and packaging scripts (`package.sh`, `package-win.bat`). Env at `frontend/.env(.example)`.
- `rag_corrections_db/`: Default ChromaDB directory for correction storage (created on first run).
- `dist/` and `build/`: Packaging outputs (PyInstaller artifacts, bundled `.env`).
- `.github/workflows/`: CI for multi-OS desktop builds and releases.

## Build, Test, and Development Commands
- Start API (auto-reload): `make server` or `uvicorn backend.server:app --reload`.
- Run desktop client: `make client` or `python -m frontend.client`.
- Docker (API only): `make docker-build` then `make docker-run`.
- Package desktop app: `make package` (Linux/macOS) or `make package-win` on Windows.
- Env setup: `cp backend/.env.example backend/.env && cp frontend/.env.example frontend/.env`.
- Chrome for dev: `google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-9222`.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8 (4-space indentation). Prefer type hints and concise docstrings for public functions.
- Naming: modules/files `snake_case.py`; classes `PascalCase`; functions/variables `snake_case`.
- Structure new code under the relevant package (`backend/` for API/LLM, `frontend/` for UI/Selenium). Avoid coupling client Selenium with backend code.
- Logging over prints; keep side effects isolated for testability.

## Testing Guidelines
- No formal suite yet; prefer `pytest` for new/changed code.
- Test layout: `tests/` or `<pkg>/tests/` with files like `test_process_fax.py`, `test_server_routes.py`.
- Run tests (if added): `pytest -q`.
- For FastAPI, use `TestClient`; for Selenium, isolate pure logic and mock WebDriver where possible.

## Commit & Pull Request Guidelines
- Commits: imperative mood with scope, e.g., `backend: add /health route`, `frontend: fix chromedriver discovery`.
- PRs: include summary, linked issues, test/run steps, and relevant screenshots (UI flows). Keep diffs focused; update README when behavior changes.
- CI: ensure GitHub Actions build artifacts succeed across OS targets before merge.

## Security & Configuration Tips
- Never commit secrets. Place API keys in `backend/.env` and runtime overrides in `frontend/.env` or `dist/.env` (macOS: `dist/FaxAutomationClient.app/Contents/MacOS/.env`).
- Backend does not run Selenium; keep browser automation in the client. Place a matching `chromedriver` next to the packaged executable (the client ignores `CHROMEDRIVER_PATH`).
