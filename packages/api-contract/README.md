# @marketmind/api-contract

`openapi.json` is generated from the FastAPI app and is the single source of truth for
the HTTP contract between `apps/api` and `apps/web`.

```bash
# after changing API schemas
cd apps/api && uv run python scripts/export_openapi.py
cd apps/web && npm run gen:api
```

CI runs both with `--check`/diff so a stale contract fails the build.
