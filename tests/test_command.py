import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import parquet_info
import parquet_windows


@pytest.mark.parametrize("arguments,expected", [
    (["dati con spazi.parquet"], ["dati con spazi.parquet", "--browse"]),
    (["dati.parquet", "--columns", "id,nome"], ["dati.parquet", "--columns", "id,nome", "--browse"]),
    (["dati.parquet", "--schema-only"], ["dati.parquet", "--schema-only"]),
    (["dati.parquet", "--format=json"], ["dati.parquet", "--format=json"]),
    (["dati.parquet", "--browse"], ["dati.parquet", "--browse"]),
    (["dati.parquet", "--color"], ["dati.parquet", "--color", "--browse"]),
    (["--version"], ["--version"]),
])
def test_command_defaults_to_interactive_and_respects_reports(monkeypatch, arguments, expected):
    received = []
    monkeypatch.setattr(sys, "argv", ["parquet", *arguments])
    monkeypatch.setattr(parquet_windows, "cli_main", lambda args: received.append(args) or 0)
    assert parquet_windows.main() == 0
    assert received == [expected]


def test_browser_navigation_keeps_selected_cell_in_bounds(tmp_path, monkeypatch):
    table = pa.table({"id": range(300), "name": ["x"] * 300})
    path = tmp_path / "data.parquet"
    pq.write_table(table, path)
    with pq.ParquetFile(path) as parquet:
        browser = parquet_info.TableBrowser(path, table, parquet.metadata, parquet_info.Palette(False), 32, 300)
    for key in ["down"] * 350 + ["right"] * 10:
        browser._handle_key(key)
    assert (browser.selected_row, browser.selected_col) == (299, 1)
    browser._handle_key("r")
    assert (browser.selected_row, browser.selected_col, browser.row_offset, browser.col_offset) == (0, 0, 0, 0)


def test_terminal_file_selection_accepts_number_and_quoted_path(tmp_path, monkeypatch):
    file = tmp_path / "file con spazi.parquet"
    file.touch()
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert parquet_windows.choose_file(tmp_path) == str(file)
    monkeypatch.setattr("builtins.input", lambda _: f'"{file}"')
    assert parquet_windows.choose_file(tmp_path) == str(file)
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert parquet_windows.choose_file(tmp_path) is None


def test_filter_keeps_source_row_numbers_and_can_be_cleared(tmp_path):
    table = pa.table({"id": [1, 2, 3, 4], "name": ["Alfa", "BETA", None, "Beta"]})
    path = tmp_path / "data.parquet"
    pq.write_table(table, path)
    with pq.ParquetFile(path) as file:
        browser = parquet_info.TableBrowser(path, table, file.metadata, parquet_info.Palette(False), 32, 4)
    browser.set_filter("beta")
    assert browser.row_ids == [1, 3]
    assert "row 2/4" in browser._detail_line()
    browser._handle_key("down")
    assert "row 4/4" in browser._detail_line()
    browser.set_filter("no match")
    assert browser.rows == []
    assert "No rows match" in browser._detail_line()
    browser._handle_key("c")
    assert browser.rows == browser.original_rows
    assert browser.row_ids == [0, 1, 2, 3]


def test_filter_editing_treats_quit_as_text_and_escape_as_cancel(tmp_path):
    table = pa.table({"name": ["query", "other"]})
    path = tmp_path / "data.parquet"
    pq.write_table(table, path)
    with pq.ParquetFile(path) as file:
        browser = parquet_info.TableBrowser(path, table, file.metadata, parquet_info.Palette(False), 32, 2)
    for key in ["/", "q", "u", "x", "backspace", "enter"]:
        browser._handle_key(key)
    assert browser.filter_text == "qu"
    assert browser.row_ids == [0]
    for key in ["/", "x", "escape"]:
        browser._handle_key(key)
    assert browser.filter_text == "qu"
    assert not browser.filter_editing


def test_terminal_control_characters_are_not_executed():
    assert parquet_info.stringify_value("\x1b[2J\x07") == "\\x1b[2J\\x07"
