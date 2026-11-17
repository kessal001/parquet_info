# Release Process

Windows releases are published on GitHub. PyPI publication is a separate opt-in operation.

## GitHub Windows release

1. Run the CLI tests and build the portable executable with `scripts/build_windows.ps1`.
2. Confirm the Python version matrix and Windows build pass on the release commit.
3. Test the actual executable: `parquet --version`, interactive navigation, colored text, filtering, and JSON output.
4. Package the executable, demo, PATH installer, instructions, project license, third-party notices and SHA-256 checksum into `parquet-info-windows-x64.zip`.
5. Create a tag for the version, for example `v0.2.0`, at the tested commit and push it.
6. Create a GitHub release for that tag. Attach `parquet.exe`, the ZIP, `SHA256SUMS.txt` and `THIRD-PARTY-NOTICES.txt`.
7. Download the published assets and verify their checksums. Confirm the README's direct download links work without signing in.

State that the executable is Windows x64 and unsigned, includes its runtime, loads 1,000 rows by default, and filters only the loaded rows.

Pushing a version tag runs the Windows build but does not publish to PyPI.

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
6. After ownership and the trusted publisher are verified, run the **Publish to PyPI (manual)** workflow against the version tag, explicitly enabling `publish_pypi`:

```powershell
gh workflow run release.yml --ref v0.2.0 -f publish_pypi=true
```

The manual workflow builds the Python package and publishes it to the separately configured PyPI project.
