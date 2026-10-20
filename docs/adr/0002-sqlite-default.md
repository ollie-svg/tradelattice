# ADR 0002: SQLite by default

Status: Accepted

## Context
A single user should get value with no infrastructure. Production users may need a server database.

## Decision
The API stores records in a single `records` table using SQLAlchemy 2. The default is a local SQLite file (`opengoods.db`); setting `DATABASE_URL` selects another database such as Postgres.

## Consequences
- Zero-setup quickstart and in-memory SQLite for tests.
- Code must avoid database-specific features; type-specific attributes live in a JSON column.
- Search (`q`) is a simple substring match in v0.1.
