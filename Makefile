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
	docker run --rm -p $(API_PORT):8000 --env-file backend/.env fax-backend

package:
	bash ./frontend/package.sh

.PHONY: package-linux package-mac package-win

# Explicit OS targets for clarity/consistency
package-linux:
	bash ./frontend/package.sh

package-mac:
	bash ./frontend/package.sh

# Run this on a Windows machine (or via CI)
package-win:
	@echo "On Windows, run: frontend\\package-win.bat"
	@echo "Or in CI, the workflow runs: pyinstaller FaxAutomationClient.spec"
