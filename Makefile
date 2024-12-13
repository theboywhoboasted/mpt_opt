# Global Variables
PROJECT_TAG = webapp/mpt

install:
	pip install --quiet -r requirements.txt

build-dev:
	docker build --quiet --tag=$(PROJECT_TAG) -f Dockerfile.dev .

build-prod:
	docker build --quiet --tag=$(PROJECT_TAG) -f Dockerfile.prod .

build: build-dev build-prod

format:
	black src/

lint:
	black --check src/ # check if the code is formatted
	ruff check src/ # fast python static checker
	docker run --rm -i hadolint/hadolint < Dockerfile.dev
	docker run --rm -i hadolint/hadolint < Dockerfile.prod
	PYTHONPATH=src pylint src/ --disable=R,C
	pyright src/
	cd src/ && mypy . && cd ..
	
all: install build lint
