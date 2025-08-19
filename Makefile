.PHONY: server client docker-build docker-run package

PYTHON ?= python
UVICORN ?= uvicorn
APP ?= backend.server:app
API_PORT ?= 8000

server:
	$(UVICORN) $(APP) --host 0.0.0.0 --port $(API_PORT) --reload

client:
	$(PYTHON) -m frontend.client

docker-build:
	docker build -f backend/Dockerfile -t fax-backend .

docker-run:
	docker run --rm -p $(API_PORT):8000 --env-file .env fax-backend

package:
	bash ./frontend/package.sh
