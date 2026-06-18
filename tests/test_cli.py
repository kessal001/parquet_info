from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "parquet_info.py"
TEST_TMP = ROOT / ".tmp-tests"


@pytest.fixture
def case_dir() -> Path:
    path = TEST_TMP / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_parquet(path: Path) -> None:
    table = pa.table(
        {
            "sku": ["A100", "B200", "C300", "D400"],
            "name": ["Espresso", "Cold brew", "Matcha", None],
            "quantity": [10, 0, 7, None],
            "status": ["ready", "backorder", "ready", "quality_hold"],
            "notes": [None, "priority reorder", "damaged box", "priority review"],
        }
    )
    pq.write_table(table, path)


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_schema_only_plain_output(case_dir: Path) -> None:
    parquet_path = case_dir / "sample.parquet"
    write_parquet(parquet_path)

    result = run_cli(str(parquet_path), "--schema-only", "--format", "plain")

    assert result.returncode == 0
    assert "Rows: 4" in result.stdout
    assert "Columns: 5" in result.stdout
    assert "sku: string" in result.stdout
    assert result.stderr == ""


def test_json_output_includes_profile_and_sample(case_dir: Path) -> None:
    parquet_path = case_dir / "sample.parquet"
    write_parquet(parquet_path)

    result = run_cli(
        str(parquet_path),
        "--format",
        "json",
        "--profile",
        "--columns",
        "sku,quantity,status",
        "--rows",
        "2",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["rows"] == 4
    assert [column["name"] for column in payload["schema"]] == [
        "sku",
        "name",
        "quantity",
        "status",
        "notes",
    ]
    assert [row["sku"] for row in payload["rows_sample"]] == ["A100", "B200"]
    assert {profile["name"] for profile in payload["profile"]} == {"sku", "quantity", "status"}


def test_search_limits_results_and_reports_scanned_rows(case_dir: Path) -> None:
    parquet_path = case_dir / "sample.parquet"
    write_parquet(parquet_path)

    result = run_cli(
        str(parquet_path),
        "--format",
        "json",
        "--search",
        "priority",
        "--search-limit",
        "1",
        "--columns",
        "sku,notes",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["search_scanned_rows"] == 4
    assert len(payload["rows_sample"]) == 1
    assert payload["rows_sample"][0]["sku"] == "B200"


def test_missing_column_returns_error(case_dir: Path) -> None:
    parquet_path = case_dir / "sample.parquet"
    write_parquet(parquet_path)

    result = run_cli(str(parquet_path), "--columns", "missing", "--format", "plain")

    assert result.returncode == 1
    assert "ERROR: columns not found: missing" in result.stderr


def test_invalid_file_returns_error(case_dir: Path) -> None:
    invalid_path = case_dir / "not.parquet"
    invalid_path.write_text("not parquet", encoding="utf-8")

    result = run_cli(str(invalid_path), "--schema-only", "--format", "plain")

    assert result.returncode == 1
    assert "ERROR: unable to read" in result.stderr
