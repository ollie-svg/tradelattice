PY ?= python

.PHONY: test serve load-samples validate lint

test:
	$(PY) -m pytest

lint:
	ruff check .

validate:
	$(PY) -m spec.validate spec/examples/*.json

load-samples:
	$(PY) -m connectors.cbsa_tariff --out records.jsonl
	$(PY) -m connectors.canadabuys --out records.jsonl.tmp && cat records.jsonl.tmp >> records.jsonl && rm records.jsonl.tmp
	$(PY) -m connectors.statcan_trade --out records.jsonl.tmp && cat records.jsonl.tmp >> records.jsonl && rm records.jsonl.tmp
	$(PY) -m api.cli load records.jsonl

serve:
	$(PY) -m uvicorn api.main:app --reload --port 8000
