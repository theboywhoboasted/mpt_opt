# Global Variables
PROJECT_TAG = webapp/mpt
VENV_DIR = .venv

install:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install --quiet -r requirements.txt -r dev-requirements.txt

build-dev:
	docker build --quiet --tag=$(PROJECT_TAG) -f Dockerfile.dev .

build-prod:
	docker build --quiet --tag=$(PROJECT_TAG) -f Dockerfile.prod .

build: build-dev build-prod

format:
	. $(VENV_DIR)/bin/activate && black src/

lint:
	. $(VENV_DIR)/bin/activate && (\
	black --check src/;\
	ruff check src/;\
	docker run --rm -i hadolint/hadolint < Dockerfile.dev;\
	docker run --rm -i hadolint/hadolint < Dockerfile.prod;\
	PYTHONPATH=src pylint src/ --disable=R,C;\
	pyright src/;\
	cd src/ && mypy . && cd ..;\
	)

all: install build lint
