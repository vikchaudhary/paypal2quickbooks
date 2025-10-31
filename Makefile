.PHONY: setup test dev-backend convert

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	. .venv/bin/activate && pip install -e backend

test:
	. .venv/bin/activate && pytest -q backend/tests

dev-backend:
	. .venv/bin/activate && uvicorn paypal2quickbooks.api.app:app --reload

convert:
	. .venv/bin/activate && paypal2quickbooks convert
