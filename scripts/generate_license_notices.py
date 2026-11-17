"""Collect redistribution notices from the isolated build environment."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
from pathlib import Path
import sys


def generate(destination: Path) -> None:
    sections = [
        "PARQUET-INFO — THIRD-PARTY NOTICES\n"
        "These notices cover runtime dependencies and build tools. Some components\n"
        "are used only when building and are not included in the executable.\n"
        "The application itself is distributed under the accompanying MIT LICENSE.\n"
    ]
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("Python redistribution license not found in the build environment")
    sections.append(f"Python {sys.version.split()[0]}\n\n{python_license.read_text(encoding='utf-8', errors='replace')}")
    covered = set()
    distributions = sorted(metadata.distributions(), key=lambda d: d.metadata.get("Name", "").casefold())
    for distribution in distributions:
        name = distribution.metadata.get("Name", "unknown")
        if name.casefold() == "parquet-info":
            continue
        for file in sorted(distribution.files or [], key=str):
            if not Path(str(file)).name.upper().startswith(("LICENSE", "COPYING", "NOTICE", "AUTHORS")):
                continue
            source = Path(distribution.locate_file(file))
            if not source.is_file():
                continue
            sections.append(f"{name} {distribution.version} — {file}\n\n{source.read_text(encoding='utf-8', errors='replace')}")
            covered.add(name.casefold())
    missing = {"pyarrow", "rich", "pyinstaller"} - covered
    if missing:
        raise ValueError("Missing redistribution notices: " + ", ".join(sorted(missing)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(("\n\n" + "=" * 78 + "\n\n").join(sections), encoding="utf-8")
    print(f"Wrote third-party notices for Python and {len(covered)} packages.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    generate(parser.parse_args().output)
