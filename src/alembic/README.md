To create a new migration

```bash
uv run alembic revision --autogenerate -m "Some message"
```

To migrate

```bash
uv run alembic upgrade head
```

To check current migration

```bash
uv run alembic current
```

To downgrade **(data will be lost)**

```bash
uv run downgrade base
```
