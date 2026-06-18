# Release Process

This project is ready for PyPI Trusted Publishing through GitHub Actions.

## One-time PyPI setup

Create a PyPI project named `parquet-info`, then add a trusted publisher with:

- owner: `kessal001`
- repository: `parquet_info`
- workflow: `release.yml`
- environment: `pypi`

## Release checklist

1. Update `__version__` in `parquet_info.py`.
2. Update `version` in `pyproject.toml`.
3. Move entries from `CHANGELOG.md` `[Unreleased]` into the new version.
4. Run:

```powershell
python -m py_compile parquet_info.py scripts\generate_demo_parquet.py scripts\generate_readme_assets.py
pytest
python -m build
```

5. Commit the release changes.
6. Create and push a tag:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

The `Release` workflow builds the package and publishes it to PyPI.
