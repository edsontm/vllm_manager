# backend/alembic/

## Purpose
Alembic database migration environment for the PostgreSQL schema. Ensures schema changes are tracked, versioned, and reproducible across all environments.

## Structure
```
backend/alembic/
├── env.py           Async migration env using asyncpg
├── script.py.mako   Migration script template
└── versions/        Auto-generated and hand-edited migration files
    └── 0001_initial_schema.py
```

## Usage

```bash
# inside the backend container or with the venv active

# Generate a migration from ORM changes
alembic revision --autogenerate -m "add_expires_at_to_access_tokens"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Show current revision
alembic current
```

## Conventions
- Migrations are auto-generated from ORM models (`--autogenerate`) and then reviewed before committing.
- Every migration file must be idempotent when possible (use `IF NOT EXISTS` / `IF EXISTS` guards).
- Never modify an already-applied migration; create a new one instead.
- The `env.py` reads `DATABASE_URL` from `settings` (not hardcoded).

## Initial Schema (`0001_initial_schema.py`)
Creates tables: `users`, `access_tokens`, `vllm_instances`, `request_logs` plus all indexes described in the respective model `.md` files.
