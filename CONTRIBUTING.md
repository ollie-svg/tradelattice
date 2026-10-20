# Contributing to OpenGoods

Thanks for helping. The project is schema-first: the data model in `spec/` is the product.

## Setup

```
pip install -e .[dev]
make test
ruff check .
```

## Ways to contribute

- **New connector**: add `connectors/<name>/` exposing `fetch(since)` and a `python -m connectors.<name>` CLI. It must work offline from a bundled sample in `connectors/<name>/sample/`; live fetching is opt-in via `--live`. See ADR 0003.
- **Schema changes**: open an issue first. Follow the versioning policy in `spec/README.md`; breaking changes need an ADR.
- **Bugs and docs**: small pull requests are welcome without prior discussion.

## Pull requests

1. Keep changes focused; add or update tests.
2. Run `ruff check .` and `pytest` and `python -m spec.validate spec/examples/*.json`.
3. Describe what changed and why.

By contributing you agree your work is licensed under Apache-2.0. All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
