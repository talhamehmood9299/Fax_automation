# Fax Automation

Automates processing of incoming faxes in talkEHR using Selenium, an LLM pipeline, and a small RAG correction store. Supports two modes:

- Normal Mode: Fully automated loop that processes faxes using `run_once()`.
- Training Mode: Processes a fax via `run_once()`, then pauses so you can save corrections (e.g., doc_type/doc_subtype) to the RAG store before moving to the next fax.

The app is split into a FastAPI backend and a Tkinter frontend client.

---

## Architecture

- Backend (`backend/`)
  - `server.py`: FastAPI server exposing LLM processing and RAG endpoints (no Selenium).
  - `process_fax.py`: LLM graph pipeline with RAG correction application.
  - `ollama_agent.py`: OpenAI-based extract/classify/comment prompts.
  - `correction_store_rag.py`: ChromaDB-powered RAG store for corrections.
- Frontend (`frontend/`)
  - `client.py`: Tkinter GUI that runs Selenium locally and calls backend `/process_url` + save-correction API.
  - `talkehr_agent.py` and `helper.py`: Selenium bot + utilities.
  

---

## Prerequisites

- Python 3.10+
- Google Chrome and matching `chromedriver` binary
- Tesseract OCR installed and on PATH (used by `docling`)
- An OpenAI API key (set in `.env`)

Note: The frontend (desktop app) attaches to a running Chrome instance launched with remote debugging. Start Chrome like this before running the client:

```
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-9222
```

---

## Setup

Recommended: install backend and frontend deps separately.

Backend (API server):
```
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Frontend (desktop client for development runs):
```
python -m venv .venv
source .venv/bin/activate
pip install -r frontend/requirements.txt
```

Copy the sample envs and edit values (no root .env):

```
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Environment keys supported

- Backend (`backend/.env`):
  - `OPENAI_API_KEY`: your OpenAI API key
  - `RAG_DB_DIR`: directory where the Chroma RAG DB persists (default `rag_corrections_db`)
  - Optional tool paths like `TESSERACT_CMD`
- Frontend (`frontend/.env`):
  - Note: The client no longer reads `CHROMEDRIVER_PATH`; it auto-discovers a driver next to the built binary in `dist/` (or on PATH as fallback).
  - You can customize UI behavior in code; `.env` is optional for the client.

### Frontend Env Loading (Build vs Runtime)

- Packaging (`make package` or `frontend/package.sh`) does not require a client `.env`.
- The client uses built-in defaults for its settings. You can adapt the code if you need runtime overrides.

---

## Running

1) Start Chrome in remote debugging mode (see above).

2) Start the backend server (no Selenium):

```
uvicorn backend.server:app --reload
```

3) Start the frontend client (Selenium + UI):

```
python -m frontend.client
```

 

### Run backend in Docker (no Selenium)

Build the image:

```
docker build -f backend/Dockerfile -t fax-backend .
```

Run the container:

```
docker run --rm -p 8000:8000 \
  --env-file backend/.env \
  fax-backend
```

Notes:
- Backend does not run Selenium. It only processes Markdown and stores corrections.
- Use the Makefile for shortcuts: `make docker-build`, `make docker-run`, `make server`, `make client`, `make package`.

### ChromeDriver Location (Unified Across OS)

The client auto-discovers ChromeDriver using this order:
- Same directory as the built app (Windows/Linux: `dist/`, macOS: `dist/FaxAutomationClient.app/Contents/MacOS/`)
- `dist/` in the repo (when running from source)
- Current working directory
- Repo root and `frontend/`
- On `PATH` (Selenium Manager/system install)

Packaging scripts copy `chromedriver` next to the built binary so the directory is the same across OS builds:
- Linux/macOS: `frontend/package.sh` copies `./chromedriver` to `dist/` (macOS inside the `.app/Contents/MacOS`)
- Windows: `frontend/package-win.bat` copies `chromedriver.exe` to `dist/`

Note: `CHROMEDRIVER_PATH` is ignored by the client.

### Run with Docker Compose

Build and start the backend API:

```
docker compose up --build -d
```

Tail logs:

```
docker compose logs -f backend
```

Stop and remove:

```
docker compose down
```

---

## Using the App

- Normal Mode (frontend):
  - Click “Start Normal Mode” to begin the automated loop.
  - “Refresh Status” shows loop state; “Stop Normal” stops it.

- Training Mode (frontend):
  - Click “Next Fax” to process a single fax (uses the same `run_once()` as Normal).
  - Predicted `doc_type` and `doc_subtype` appear in the UI.
  - Optionally edit the corrected values and click “Save Correction”.
  - Click “Next Fax” to move on; previous corrections are applied automatically by RAG.

- Health Check:
  - Click “Health Check” to verify the backend is reachable.

---

## How It Works

1. `TalkEHRBot` navigates talkEHR to fetch the current/next fax URL.
2. `doc_agent.convert_document()` converts the PDF to Markdown text.
3. `process_fax()` runs the LLM pipeline to extract fields and then applies any known corrections from the RAG store.
4. The bot fills fields in talkEHR and saves the document.
5. In Training Mode, the client pauses between faxes so you can store corrections into the RAG store (ChromaDB + Sentence Transformers). Future similar faxes then auto-correct.

---

## Repository Structure

```
backend/
  __init__.py
  server.py
  process_fax.py
  ollama_agent.py
  correction_store_rag.py
frontend/
  __init__.py
  client.py
  helper.py
  talkehr_agent.py
requirements.txt
.env.example           # copy to .env and edit
```

---

## Troubleshooting

- Chrome Attach Fails:
  - Ensure Chrome was launched with `--remote-debugging-port=9222` and your `DEBUGGER_ADDRESS` matches.
- Ensure a matching ChromeDriver is next to the built app or on PATH. The client ignores `CHROMEDRIVER_PATH`.

- OCR/Doc Conversion Issues:
  - Ensure Tesseract is installed and on PATH; `docling` expects it. You can set the command in code if needed.

- OpenAI Errors:
  - Set `OPENAI_API_KEY` in `.env`. Ensure your network/firewall allows API access.

- RAG Store Problems:
  - Check `RAG_DB_DIR` permissions and disk space. The first run will download the embedding model.

- Backend Unreachable:
  - Use the frontend “Health Check” or `curl http://127.0.0.1:8000/health` to confirm the server is up.

---

## Notes

- Training Mode uses the exact same `run_once()` as Normal Mode; the only difference is the pause to let you save corrections before continuing.
- For production or multi-user setups, consider securing the FastAPI server and running it behind a proper process manager.

---

## Desktop Build (Frontend)

Package the Tkinter client into a single-file desktop app using PyInstaller:

```
pip install pyinstaller
bash frontend/package.sh
```

Artifacts:
- Single file: `dist/FaxAutomationClient` (Linux/macOS) or `dist/FaxAutomationClient.exe` (Windows)
- Windows build on Windows host: run `frontend\package-win.bat`
  - PyInstaller does not cross-compile; to get a `.exe` you must build on Windows.
  - Ensure the same Python and dependency versions on Windows before packaging.

### CI Builds (GitHub Actions)

This repo includes a workflow that builds native binaries on Windows, macOS, and Ubuntu using GitHub-hosted runners.

- Trigger: Push to `main`/`master`, pull requests, or manual via “Run workflow”.
- Location: GitHub → Actions → “Build Desktop Apps”.
- Output: Per-OS artifacts uploaded from `dist/` as `FaxAutomationClient-<OS>`.

Notes:
- PyInstaller uses platform-specific bootloaders, so each OS is built on its native runner.
- These builds package only the frontend and its minimal dependencies; the backend and heavy ML libs are not part of the desktop binary.
