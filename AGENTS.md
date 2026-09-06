# Agent guide

This repository is a code-managed Pipecat Cloud receptionist using Twilio Media Streams.

## Work locally

- Use Python 3.12 and `uv` only.
- Keep credentials in `.env`; update `.env.example` with names, never values.
- Keep transport and call lifecycle code in `receptionist/app.py`.
- Keep conversation tools in `receptionist/tools.py`.
- Keep business-hours logic in `receptionist/hours.py`.
- Keep provider HTTP boundaries in their provider modules.

## Validate

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run python -m unittest discover -s tests
```

Do not deploy or change Twilio routing until every check passes.
