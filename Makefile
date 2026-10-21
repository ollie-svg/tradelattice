PY ?= python

.PHONY: test serve load-samples validate lint docs docs-serve

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

docs:
	mkdocs build --strict

docs-serve:
	mkdocs serve

.PHONY: edition-check edition-diff

edition-check:
	$(PY) -m connectors.cbsa_tariff check --state data/cbsa_edition.json

# usage: make edition-diff OLD=old.jsonl NEW=new.jsonl
edition-diff:
	@test -n "$(OLD)" -a -n "$(NEW)" || (echo "usage: make edition-diff OLD=old.jsonl NEW=new.jsonl" && exit 2)
	$(PY) -m connectors.cbsa_tariff diff $(OLD) $(NEW) --markdown
