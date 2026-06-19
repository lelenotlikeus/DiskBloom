# Contributing

Thanks for helping improve DiskBloom.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
python main.py
```

Use `.venv\Scripts\activate` on Windows.

## Guidelines

- Keep core filesystem logic separate from UI code.
- Prefer clear Python and type hints over clever abstractions.
- Do not add web stacks, Electron, npm, Rust, or fake scan data.
- Add focused tests for scanner, formatting, filtering, or classification changes.
- Keep deletion safe: use `send2trash` unless a future feature explicitly adds a separate advanced mode.

## Pull Requests

Include a short summary, screenshots for UI changes, and test results.
