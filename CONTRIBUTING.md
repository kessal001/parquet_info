# Contributing

Thanks for helping improve `parquet-info`.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Checks

Run the same checks used by CI:

```powershell
python -m py_compile parquet_info.py scripts\generate_demo_parquet.py scripts\generate_readme_assets.py
pytest
```

## Pull requests

- Keep changes focused on one behavior or documentation improvement.
- Add or update tests for CLI behavior, JSON output, search, profiling, and edge cases.
- Regenerate README assets when terminal output formatting changes:

```powershell
python scripts\generate_readme_assets.py
```

## Good first issues

Useful entry points include:

- adding tests for Arrow data types not covered yet;
- improving terminal table rendering on narrow screens;
- documenting real-world inspection workflows;
- profiling performance on large files.
