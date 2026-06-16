from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

box = None
Console = None
Panel = None
Table = None
RICH_AVAILABLE: bool | None = None


ANSI_SEQUENCE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass
class ColumnProfile:
    name: str
    type: str
    rows: int
    valid: int
    nulls: int
    null_percent: float
    distinct: int | None
    min: str
    max: str
    mean: str
    top_values: str


class Palette:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def paint(self, text: str, code: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"


def enable_ansi(no_color: bool = False) -> bool:
    if no_color or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False

    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:  # noqa: BLE001 - colors are optional.
            pass

    return True


def format_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def stringify_value(value: object) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.hex()
    elif isinstance(value, (datetime, date, time, Decimal)):
        text = str(value)
    else:
        text = str(value)

    return text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", " ")


def clip_text(text: str, max_width: int) -> str:
    if max_width > 0 and len(text) > max_width:
        if max_width <= 3:
            return text[:max_width]
        return text[: max_width - 3] + "..."
    return text


def truncate(value: object, max_width: int) -> str:
    return clip_text(stringify_value(value), max_width)


def format_percent(value: float) -> str:
    if value == 0:
        return "0%"
    if value == 100:
        return "100%"
    return f"{value:.2f}%"


def format_number(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}".replace(",", ".")


def json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (datetime, date, time, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return str(value)


def scalar_text(value: object, max_width: int = 80) -> str:
    return clip_text(stringify_value(value), max_width)


def load_rich() -> bool:
    global RICH_AVAILABLE, box, Console, Panel, Table

    if RICH_AVAILABLE is not None:
        return RICH_AVAILABLE

    try:
        from rich import box as rich_box
        from rich.console import Console as RichConsole
        from rich.panel import Panel as RichPanel
        from rich.table import Table as RichTable
    except Exception:  # noqa: BLE001 - rich is an optional presentation layer.
        RICH_AVAILABLE = False
        return False

    box = rich_box
    Console = RichConsole
    Panel = RichPanel
    Table = RichTable
    RICH_AVAILABLE = True
    return True


def expand_paths(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(pattern))
    return paths


def schema_lines(schema: pa.Schema) -> list[str]:
    width = len(str(len(schema)))
    lines = []
    for index, field in enumerate(schema, start=1):
        nullable = "nullable" if field.nullable else "not null"
        lines.append(f"  {index:{width}d}. {field.name}: {field.type} ({nullable})")
    return lines


def read_rows(parquet_file: pq.ParquetFile, rows: int, columns: list[str] | None) -> pa.Table | None:
    if rows <= 0:
        table = parquet_file.read(columns=columns)
        return table if table.num_rows > 0 else None

    batches: list[pa.RecordBatch] = []
    remaining = rows
    try:
        for batch in parquet_file.iter_batches(batch_size=min(remaining, 8192), columns=columns):
            if batch.num_rows > remaining:
                batch = batch.slice(0, remaining)
            batches.append(batch)
            remaining -= batch.num_rows
            if remaining <= 0:
                break
    except StopIteration:
        pass

    if not batches:
        return None
    return pa.Table.from_batches(batches)


def read_sample(parquet_file: pq.ParquetFile, rows: int, columns: list[str] | None) -> pa.Table | None:
    if rows <= 0:
        return None
    return read_rows(parquet_file, rows, columns)


def is_numeric_type(data_type: pa.DataType) -> bool:
    return (
        pa.types.is_integer(data_type)
        or pa.types.is_floating(data_type)
        or pa.types.is_decimal(data_type)
    )


def compute_top_values(array: pa.ChunkedArray, limit: int) -> str:
    if limit <= 0 or len(array) == 0:
        return "-"

    non_null = pc.drop_null(array)
    if len(non_null) == 0:
        return "-"

    try:
        counts = pc.value_counts(non_null).to_pylist()
    except Exception:  # noqa: BLE001 - not all Arrow types support value_counts.
        return "-"

    items: list[tuple[str, int]] = []
    for item in counts:
        value = item.get("values")
        count = int(item.get("counts") or 0)
        items.append((scalar_text(value, 36), count))

    items.sort(key=lambda item: (-item[1], item[0].lower()))
    return "; ".join(f"{value} ({format_number(count)})" for value, count in items[:limit]) or "-"


def empty_profile(name: str, data_type: pa.DataType) -> ColumnProfile:
    return ColumnProfile(name, str(data_type), 0, 0, 0, 0.0, None, "-", "-", "-", "-")


def profile_array(name: str, data_type: pa.DataType, array: pa.ChunkedArray, top_values: int) -> ColumnProfile:
    total = len(array)
    nulls = array.null_count
    valid = total - nulls
    null_percent = (nulls / total * 100) if total else 0.0
    distinct: int | None = None
    min_value = "-"
    max_value = "-"
    mean_value = "-"

    if valid:
        try:
            distinct_value = pc.count_distinct(array, mode="only_valid").as_py()
            distinct = int(distinct_value) if distinct_value is not None else None
        except Exception:  # noqa: BLE001 - keep profiling resilient per column.
            distinct = None

        try:
            min_max = pc.min_max(pc.drop_null(array)).as_py()
            min_value = scalar_text(min_max.get("min"))
            max_value = scalar_text(min_max.get("max"))
        except Exception:  # noqa: BLE001
            min_value = "-"
            max_value = "-"

        if is_numeric_type(data_type):
            try:
                mean_raw = pc.mean(array).as_py()
                mean_value = scalar_text(mean_raw)
            except Exception:  # noqa: BLE001
                mean_value = "-"

    return ColumnProfile(
        name=name,
        type=str(data_type),
        rows=total,
        valid=valid,
        nulls=nulls,
        null_percent=null_percent,
        distinct=distinct,
        min=min_value,
        max=max_value,
        mean=mean_value,
        top_values=compute_top_values(array, top_values),
    )


def profile_column(parquet_file: pq.ParquetFile, name: str, rows: int, top_values: int) -> ColumnProfile:
    data_type = parquet_file.schema_arrow.field(name).type
    table = read_rows(parquet_file, rows, [name])
    if table is None:
        return empty_profile(name, data_type)

    return profile_array(name, data_type, table.column(name), top_values)


def profile_columns(
    parquet_file: pq.ParquetFile,
    columns: list[str],
    rows: int,
    top_values: int,
) -> list[ColumnProfile]:
    schema = parquet_file.schema_arrow
    try:
        table = read_rows(parquet_file, rows, columns)
    except (MemoryError, pa.ArrowMemoryError):
        return [profile_column(parquet_file, name, rows, top_values) for name in columns]

    if table is None:
        return [empty_profile(name, schema.field(name).type) for name in columns]

    return [
        profile_array(name, schema.field(name).type, table.column(name), top_values)
        for name in columns
    ]


def searchable_column_mask(batch: pa.RecordBatch, text: str, case_sensitive: bool) -> pa.Array:
    needle = text if case_sensitive else text.lower()
    mask: pa.Array | None = None

    for column in batch.columns:
        try:
            as_text = pc.cast(column, pa.string(), safe=False)
        except Exception:  # noqa: BLE001 - skip unsupported types.
            continue

        if not case_sensitive:
            as_text = pc.utf8_lower(as_text)

        column_mask = pc.fill_null(pc.match_substring(as_text, needle), False)
        mask = column_mask if mask is None else pc.or_(mask, column_mask)

    if mask is None:
        return pa.array([False] * batch.num_rows)
    return mask


def search_rows(
    parquet_file: pq.ParquetFile,
    columns: list[str],
    text: str,
    limit: int,
    rows: int,
    case_sensitive: bool,
) -> tuple[pa.Table | None, int]:
    if limit <= 0:
        return None, 0

    batches: list[pa.RecordBatch] = []
    scanned = 0
    found = 0
    batch_size = 8192 if rows <= 0 else min(8192, max(rows, 1))

    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        if rows > 0 and scanned >= rows:
            break
        if rows > 0 and scanned + batch.num_rows > rows:
            batch = batch.slice(0, rows - scanned)

        scanned += batch.num_rows
        mask = searchable_column_mask(batch, text, case_sensitive)
        filtered = batch.filter(mask)
        if filtered.num_rows:
            remaining = limit - found
            if filtered.num_rows > remaining:
                filtered = filtered.slice(0, remaining)
            batches.append(filtered)
            found += filtered.num_rows
            if found >= limit:
                break

    if not batches:
        return None, scanned
    return pa.Table.from_batches(batches), scanned


def render_text_grid(
    headers: list[str],
    rows: list[list[str]],
    max_width: int,
    palette: Palette | None = None,
) -> list[str]:
    palette = palette or Palette(False)
    values = [[clip_text(cell, max_width) for cell in row] for row in rows]
    widths = []
    for col_index, name in enumerate(headers):
        width = len(clip_text(name, max_width))
        for row in values:
            width = max(width, len(row[col_index]))
        if max_width > 0:
            width = min(width, max_width)
        widths.append(width)

    def render_row(cells: list[str]) -> str:
        return " | ".join(cells[i].ljust(widths[i]) for i in range(len(cells)))

    separator = "-+-".join("-" * width for width in widths)
    output = [palette.paint(render_row(headers), "1;37;44"), palette.paint(separator, "36")]
    for index, row in enumerate(values):
        rendered = render_row(row)
        output.append(palette.paint(rendered, "90") if index % 2 else rendered)
    return output


def render_table(table: pa.Table, max_width: int, palette: Palette | None = None) -> list[str]:
    names = table.column_names
    rows = table.to_pylist()
    values = [[truncate(row.get(name), max_width) for name in names] for row in rows]
    return render_text_grid(names, values, max_width, palette)


def parse_columns(requested_columns: str | None, schema: pa.Schema) -> tuple[list[str], list[str]]:
    if not requested_columns:
        return list(schema.names), []

    requested = [name.strip() for name in requested_columns.split(",") if name.strip()]
    missing = [name for name in requested if name not in schema.names]
    return requested, missing


def selected_output_format(args: argparse.Namespace) -> str:
    if args.format == "auto":
        if not sys.stdout.isatty():
            return "plain"
        return "rich" if load_rich() else "plain"
    if args.format == "rich" and not load_rich():
        print("AVVISO: libreria rich non disponibile, uso output plain.", file=sys.stderr)
        return "plain"
    return args.format


def row_group_details(metadata: pq.FileMetaData) -> list[dict[str, object]]:
    groups = []
    for index in range(metadata.num_row_groups):
        group = metadata.row_group(index)
        groups.append(
            {
                "index": index,
                "rows": group.num_rows,
                "columns": group.num_columns,
                "total_byte_size": group.total_byte_size,
            }
        )
    return groups


def build_json_report(
    path: Path,
    metadata: pq.FileMetaData,
    schema: pa.Schema,
    sample: pa.Table | None,
    profiles: list[ColumnProfile],
    search_scanned_rows: int | None,
) -> dict[str, object]:
    return {
        "file": str(path),
        "file_size_bytes": path.stat().st_size,
        "rows": metadata.num_rows,
        "columns": metadata.num_columns,
        "row_groups": metadata.num_row_groups,
        "created_by": metadata.created_by,
        "schema": [
            {
                "index": index,
                "name": field.name,
                "type": str(field.type),
                "nullable": field.nullable,
            }
            for index, field in enumerate(schema, start=1)
        ],
        "row_group_details": row_group_details(metadata),
        "search_scanned_rows": search_scanned_rows,
        "profile": [asdict(profile) for profile in profiles],
        "rows_sample": [] if sample is None else json_safe(sample.to_pylist()),
    }


def profile_range_text(profile: ColumnProfile) -> str:
    parts = []
    if profile.min != "-" or profile.max != "-":
        parts.append(f"{profile.min} -> {profile.max}")
    if profile.mean != "-":
        parts.append(f"media {profile.mean}")
    return "; ".join(parts) or "-"


def render_profile_plain(profiles: list[ColumnProfile], max_width: int, palette: Palette) -> None:
    if not profiles:
        return

    headers = ["#", "Colonna", "Tipo", "Null", "Distinct", "Range / media", "Top valori"]
    rows = []
    for index, profile in enumerate(profiles, start=1):
        rows.append(
            [
                str(index),
                profile.name,
                profile.type,
                f"{format_number(profile.nulls)} ({format_percent(profile.null_percent)})",
                format_number(profile.distinct),
                profile_range_text(profile),
                profile.top_values,
            ]
        )

    print()
    print(palette.paint("Profilo colonne:", "1;35"))
    print("\n".join(render_text_grid(headers, rows, max_width, palette)))


def render_plain_report(
    path: Path,
    metadata: pq.FileMetaData,
    schema: pa.Schema,
    sample: pa.Table | None,
    sample_title: str | None,
    profiles: list[ColumnProfile],
    args: argparse.Namespace,
    search_scanned_rows: int | None,
) -> None:
    palette = Palette(args.color)
    print(palette.paint(f"=== {path} ===", "1;36"))
    print(f"{palette.paint('Dimensione file:', '1;33')} {format_bytes(path.stat().st_size)}")
    print(f"{palette.paint('Righe:', '1;33')} {metadata.num_rows:,}".replace(",", "."))
    print(f"{palette.paint('Colonne:', '1;33')} {metadata.num_columns}")
    print(f"{palette.paint('Row groups:', '1;33')} {metadata.num_row_groups}")
    print()
    print(palette.paint("Schema:", "1;35"))
    print("\n".join(schema_lines(schema)))

    render_profile_plain(profiles, args.max_width, palette)
    if profiles:
        profile_rows = metadata.num_rows if args.profile_rows == 0 else min(metadata.num_rows, args.profile_rows)
        suffix = "" if profile_rows == metadata.num_rows else f" su {format_number(metadata.num_rows)}"
        print(f"Profilo calcolato su {format_number(profile_rows)} righe{suffix}.")

    if args.schema_only:
        print()
        return

    print()
    if search_scanned_rows is not None:
        print(f"Righe scansionate per ricerca: {format_number(search_scanned_rows)}")

    if sample is None or sample.num_rows == 0:
        print("Righe: nessuna riga disponibile.")
        print()
        return

    print(palette.paint(f"{sample_title}:", "1;35"))
    print("\n".join(render_table(sample, args.max_width, palette)))
    print()


def render_rich_schema(console: "Console", schema: pa.Schema) -> None:
    table = Table(title="Schema", box=box.SIMPLE_HEAVY, row_styles=["", "dim"])
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Colonna", style="bold")
    table.add_column("Tipo", overflow="fold")
    table.add_column("Null", no_wrap=True)

    for index, field in enumerate(schema, start=1):
        table.add_row(str(index), field.name, str(field.type), "si" if field.nullable else "no")
    console.print(table)


def render_rich_profile(console: "Console", profiles: list[ColumnProfile], max_width: int) -> None:
    if not profiles:
        return

    table = Table(title="Profilo colonne", box=box.SIMPLE_HEAVY, row_styles=["", "dim"])
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Colonna", style="bold", max_width=min(max_width, 24), overflow="ellipsis", no_wrap=True)
    table.add_column("Dettagli", ratio=1, overflow="fold")

    for index, profile in enumerate(profiles, start=1):
        details = "\n".join(
            [
                f"Tipo: {profile.type}",
                f"Null: {format_number(profile.nulls)} ({format_percent(profile.null_percent)})"
                f" | Distinct: {format_number(profile.distinct)}",
                f"Range/media: {profile_range_text(profile)}",
                f"Top: {profile.top_values}",
            ]
        )
        table.add_row(
            str(index),
            profile.name,
            details,
        )
    console.print(table)


def render_rich_sample(console: "Console", sample: pa.Table | None, title: str | None, max_width: int) -> None:
    if sample is None or sample.num_rows == 0:
        console.print("[yellow]Righe: nessuna riga disponibile.[/yellow]")
        return

    table = Table(title=title, box=box.SIMPLE_HEAVY, row_styles=["", "dim"])
    for name in sample.column_names:
        table.add_column(name, max_width=max_width, overflow="ellipsis", no_wrap=True)

    for row in sample.to_pylist():
        table.add_row(*(truncate(row.get(name), max_width) for name in sample.column_names))
    console.print(table)


def render_rich_report(
    path: Path,
    metadata: pq.FileMetaData,
    schema: pa.Schema,
    sample: pa.Table | None,
    sample_title: str | None,
    profiles: list[ColumnProfile],
    args: argparse.Namespace,
    search_scanned_rows: int | None,
) -> None:
    console = Console(no_color=args.no_color, highlight=False)
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(no_wrap=True)
    summary.add_row("File", str(path))
    summary.add_row("Dimensione", format_bytes(path.stat().st_size))
    summary.add_row("Righe", format_number(metadata.num_rows))
    summary.add_row("Colonne", format_number(metadata.num_columns))
    summary.add_row("Row groups", format_number(metadata.num_row_groups))
    if metadata.created_by:
        summary.add_row("Created by", metadata.created_by)
    if profiles:
        profile_rows = metadata.num_rows if args.profile_rows == 0 else min(metadata.num_rows, args.profile_rows)
        suffix = "" if profile_rows == metadata.num_rows else f" / {format_number(metadata.num_rows)}"
        summary.add_row("Profilo righe", f"{format_number(profile_rows)}{suffix}")
    if search_scanned_rows is not None:
        summary.add_row("Ricerca righe lette", format_number(search_scanned_rows))

    console.print(Panel(summary, title=path.name, border_style="cyan"))
    render_rich_schema(console, schema)
    render_rich_profile(console, profiles, args.max_width)

    if not args.schema_only:
        render_rich_sample(console, sample, sample_title, args.max_width)
    console.print()


class KeyReader:
    def __enter__(self) -> "KeyReader":
        if os.name == "nt":
            import msvcrt

            self._msvcrt = msvcrt
            self._old_termios = None
            return self

        import termios
        import tty

        self._msvcrt = None
        self._fd = sys.stdin.fileno()
        self._old_termios = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if os.name != "nt" and self._old_termios is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_termios)

    def read(self) -> str:
        if os.name == "nt":
            ch = self._msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                code = self._msvcrt.getwch()
                return {
                    "H": "up",
                    "P": "down",
                    "K": "left",
                    "M": "right",
                    "I": "pageup",
                    "Q": "pagedown",
                    "G": "home",
                    "O": "end",
                }.get(code, "")
            if ch == "\r":
                return "enter"
            if ch == "\x1b":
                return "escape"
            return ch

        import select

        ch = sys.stdin.read(1)
        if ch != "\x1b":
            return ch

        sequence = ""
        while select.select([sys.stdin], [], [], 0.01)[0]:
            sequence += sys.stdin.read(1)
        return {
            "[A": "up",
            "[B": "down",
            "[D": "left",
            "[C": "right",
            "[5~": "pageup",
            "[6~": "pagedown",
            "[H": "home",
            "[F": "end",
            "OH": "home",
            "OF": "end",
        }.get(sequence, "escape")


class TableBrowser:
    def __init__(
        self,
        path: Path,
        table: pa.Table,
        metadata: pq.FileMetaData,
        palette: Palette,
        max_width: int,
        loaded_rows_limit: int,
    ) -> None:
        self.path = path
        self.names = table.column_names
        self.rows = self._rows_from_table(table)
        self.metadata = metadata
        self.palette = palette
        self.max_width = max_width
        self.loaded_rows_limit = loaded_rows_limit
        self.selected_row = 0
        self.selected_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.widths = self._column_widths()
        self.visible_widths: dict[int, int] = {}

    def _rows_from_table(self, table: pa.Table) -> list[list[str]]:
        py_rows = table.to_pylist()
        return [[stringify_value(row.get(name)) for name in self.names] for row in py_rows]

    def _column_widths(self) -> list[int]:
        widths: list[int] = []
        for col_index, name in enumerate(self.names):
            width = min(max(len(name), 5), self.max_width)
            for row in self.rows:
                width = max(width, min(len(row[col_index]), self.max_width))
            widths.append(width)
        return widths

    def run(self) -> None:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("ERRORE: --browse richiede un terminale interattivo.", file=sys.stderr)
            return

        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()
        try:
            with KeyReader() as keys:
                while True:
                    self._draw()
                    key = keys.read()
                    if key in ("q", "Q", "escape"):
                        break
                    self._handle_key(key)
        finally:
            sys.stdout.write("\033[?25h\033[?1049l")
            sys.stdout.flush()

    def _handle_key(self, key: str) -> None:
        body_rows = self._body_rows()
        if key in ("up", "w", "W"):
            self.selected_row = max(0, self.selected_row - 1)
        elif key in ("down", "s", "S"):
            self.selected_row = min(max(len(self.rows) - 1, 0), self.selected_row + 1)
        elif key in ("left", "a", "A"):
            self.selected_col = max(0, self.selected_col - 1)
        elif key in ("right", "d", "D"):
            self.selected_col = min(max(len(self.names) - 1, 0), self.selected_col + 1)
        elif key == "pageup":
            self.selected_row = max(0, self.selected_row - body_rows)
        elif key == "pagedown":
            self.selected_row = min(max(len(self.rows) - 1, 0), self.selected_row + body_rows)
        elif key == "home":
            self.selected_col = 0
        elif key == "end":
            self.selected_col = max(len(self.names) - 1, 0)
        elif key in ("r", "R"):
            self.selected_row = 0
            self.selected_col = 0

        self._ensure_visible()

    def _draw(self) -> None:
        width, height = shutil.get_terminal_size((120, 32))
        if width < 50 or height < 10:
            output = [
                "\033[H\033[J",
                "Terminale troppo piccolo per il browser.",
                "Allarga la finestra oppure usa l'output classico senza --browse.",
            ]
            sys.stdout.write("\n".join(output))
            sys.stdout.flush()
            return

        self._ensure_visible()
        body_rows = self._body_rows()
        visible_columns = self._visible_columns(width)

        loaded_rows = len(self.rows)
        total_rows = self.metadata.num_rows
        loaded_text = f"{loaded_rows:,}".replace(",", ".")
        total_text = f"{total_rows:,}".replace(",", ".")
        limit_note = ""
        if self.loaded_rows_limit > 0 and loaded_rows < total_rows:
            limit_note = f"  campione: prime {loaded_text} righe"

        title = self.palette.paint(f"{self.path.name}", "1;36")
        stats = (
            f"righe {loaded_text}/{total_text}  "
            f"colonne {len(self.names)}  "
            f"row groups {self.metadata.num_row_groups}"
            f"{limit_note}"
        )
        stats = self.palette.paint(stats, "33")

        lines = ["\033[H", self._fit_line(title, width), self._fit_line(stats, width)]
        lines.append(self._render_header(visible_columns, width))
        lines.append(self._render_separator(visible_columns, width))

        for display_row in range(body_rows):
            row_index = self.row_offset + display_row
            if row_index >= loaded_rows:
                lines.append("")
                continue
            lines.append(self._render_row(row_index, visible_columns, width))

        lines.append(self._fit_line(self._detail_line(), width))
        help_text = "Frecce/WASD: muovi  PagSu/PagGiu: righe  Home/End: colonne  R: inizio  Q/Esc: esci"
        lines.append(self._fit_line(self.palette.paint(help_text, "90"), width))
        lines.append("\033[J")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    def _body_rows(self) -> int:
        return max(1, shutil.get_terminal_size((120, 32)).lines - 7)

    def _row_label_width(self) -> int:
        return max(5, len(str(max(self.metadata.num_rows, len(self.rows), 1))))

    def _visible_columns(self, terminal_width: int) -> list[int]:
        self.visible_widths = {}
        if not self.names:
            return []

        available = terminal_width - self._row_label_width() - 3
        if available < 5:
            self.visible_widths[self.col_offset] = max(1, available)
            return [self.col_offset]

        indices: list[int] = []
        used = 0
        for col_index in range(self.col_offset, len(self.names)):
            col_width = min(self.widths[col_index], max(5, available))
            addition = col_width + (3 if indices else 0)
            if indices and used + addition > available:
                break
            if not indices and addition > available:
                indices.append(col_index)
                self.visible_widths[col_index] = max(1, available)
                break
            indices.append(col_index)
            self.visible_widths[col_index] = col_width
            used += addition
        return indices

    def _ensure_visible(self) -> None:
        body_rows = self._body_rows()
        if self.selected_row < self.row_offset:
            self.row_offset = self.selected_row
        elif self.selected_row >= self.row_offset + body_rows:
            self.row_offset = self.selected_row - body_rows + 1

        terminal_width = shutil.get_terminal_size((120, 32)).columns
        if self.selected_col < self.col_offset:
            self.col_offset = self.selected_col
        while self.selected_col not in self._visible_columns(terminal_width) and self.col_offset < self.selected_col:
            self.col_offset += 1

    def _render_header(self, visible_columns: list[int], terminal_width: int) -> str:
        row_label = "#".rjust(self._row_label_width())
        cells = [self._cell(self.names[index], self._display_width(index)) for index in visible_columns]
        line = f"{row_label} | " + " | ".join(cells)
        return self._fit_line(self.palette.paint(line, "1;37;44"), terminal_width)

    def _render_separator(self, visible_columns: list[int], terminal_width: int) -> str:
        row_label = "-" * self._row_label_width()
        cells = ["-" * self._display_width(index) for index in visible_columns]
        line = f"{row_label}-+-" + "-+-".join(cells)
        return self._fit_line(self.palette.paint(line, "36"), terminal_width)

    def _render_row(self, row_index: int, visible_columns: list[int], terminal_width: int) -> str:
        row_number = str(row_index + 1).rjust(self._row_label_width())
        row_number_code = "1;30;47" if row_index == self.selected_row else "90"
        cells = [self.palette.paint(row_number, row_number_code)]

        for col_index in visible_columns:
            cell = self._cell(self.rows[row_index][col_index], self._display_width(col_index))
            if row_index == self.selected_row and col_index == self.selected_col:
                cell = self.palette.paint(cell, "1;30;103")
            elif row_index == self.selected_row:
                cell = self.palette.paint(cell, "30;47")
            elif col_index == self.selected_col:
                cell = self.palette.paint(cell, "1;36")
            elif row_index % 2:
                cell = self.palette.paint(cell, "90")
            cells.append(cell)

        return self._fit_line(cells[0] + " | " + " | ".join(cells[1:]), terminal_width)

    def _detail_line(self) -> str:
        if not self.rows or not self.names:
            return self.palette.paint("Nessuna riga disponibile.", "33")

        name = self.names[self.selected_col]
        value = self.rows[self.selected_row][self.selected_col]
        position = (
            f"riga {self.selected_row + 1}/{len(self.rows)}  "
            f"colonna {self.selected_col + 1}/{len(self.names)}  "
        )
        return self.palette.paint(position, "1;36") + f"{name} = {value}"

    def _display_width(self, col_index: int) -> int:
        return self.visible_widths.get(col_index, self.widths[col_index])

    @staticmethod
    def _cell(text: str, width: int) -> str:
        return clip_text(text, width).ljust(width)

    @staticmethod
    def _fit_line(text: str, width: int) -> str:
        if len(ANSI_SEQUENCE.sub("", text)) <= width:
            return text + "\033[K"

        limit = max(0, width - 3)
        output: list[str] = []
        visible = 0
        index = 0
        while index < len(text) and visible < limit:
            match = ANSI_SEQUENCE.match(text, index)
            if match:
                output.append(match.group(0))
                index = match.end()
                continue
            output.append(text[index])
            visible += 1
            index += 1

        if width >= 3:
            output.append("...")
        output.append("\033[0m\033[K")
        return "".join(output)


def inspect_file(path: Path, args: argparse.Namespace) -> tuple[int, dict[str, object] | None]:
    if not path.exists():
        print(f"ERRORE: file non trovato: {path}", file=sys.stderr)
        return 1, None
    if not path.is_file():
        print(f"ERRORE: non e' un file: {path}", file=sys.stderr)
        return 1, None

    try:
        parquet_file = pq.ParquetFile(path)
    except Exception as exc:  # noqa: BLE001 - show concise CLI error.
        print(f"ERRORE: impossibile leggere {path}: {exc}", file=sys.stderr)
        return 1, None

    metadata = parquet_file.metadata
    schema = parquet_file.schema_arrow
    output_format = selected_output_format(args)
    sample: pa.Table | None = None
    profiles: list[ColumnProfile] = []
    sample_title: str | None = None
    search_scanned_rows: int | None = None

    if not args.schema_only:
        sample_columns, missing = parse_columns(args.columns, schema)
        if missing:
            print(f"ERRORE: colonne non trovate: {', '.join(missing)}", file=sys.stderr)
            return 1, None

        display_columns = sample_columns
        if args.max_sample_columns > 0:
            display_columns = sample_columns[: args.max_sample_columns]

        if args.profile:
            profiles = profile_columns(parquet_file, sample_columns, args.profile_rows, args.top_values)

        if args.browse:
            sample = read_rows(parquet_file, args.browse_rows, sample_columns)
            if sample is None:
                sample = pa.table({name: [] for name in sample_columns})
            TableBrowser(path, sample, metadata, Palette(args.color), args.max_width, args.browse_rows).run()
            print()
            return 0, None

        if args.search:
            sample, search_scanned_rows = search_rows(
                parquet_file,
                sample_columns,
                args.search,
                args.search_limit,
                args.search_rows,
                args.case_sensitive,
            )
            if sample is not None and display_columns != sample_columns:
                sample = sample.select(display_columns)
            sample_title = f"Prime {0 if sample is None else sample.num_rows} righe che contengono {args.search!r}"
            if len(display_columns) < len(sample_columns):
                sample_title += f" (prime {len(display_columns)} colonne visualizzate)"
        else:
            sample = read_sample(parquet_file, args.rows, display_columns)
            if sample is None:
                sample_title = "Prime righe"
            else:
                sample_title = f"Prime {sample.num_rows} righe"
            if len(display_columns) < len(schema.names):
                sample_title += f" (prime {len(display_columns)} colonne; usa --max-sample-columns 0 per tutte)"

    report = build_json_report(path, metadata, schema, sample, profiles, search_scanned_rows)
    if output_format == "json":
        return 0, report
    if output_format == "rich":
        render_rich_report(path, metadata, schema, sample, sample_title, profiles, args, search_scanned_rows)
    else:
        render_plain_report(path, metadata, schema, sample, sample_title, profiles, args, search_scanned_rows)
    return 0, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mostra schema, profilo colonne e prime righe di uno o piu' file Parquet.",
    )
    parser.add_argument("files", nargs="+", help="File o pattern, ad esempio BaseDWH.parquet oppure *.parquet")
    parser.add_argument("-n", "--rows", type=int, default=5, help="Numero di righe di esempio da mostrare (default: 5)")
    parser.add_argument("--columns", help="Colonne da mostrare nell'anteprima, separate da virgola")
    parser.add_argument(
        "--max-sample-columns",
        type=int,
        default=25,
        help="Numero massimo di colonne nell'anteprima. Usa 0 per mostrarle tutte (default: 25)",
    )
    parser.add_argument("--max-width", type=int, default=40, help="Larghezza massima per valore mostrato (default: 40)")
    parser.add_argument(
        "--format",
        choices=("auto", "rich", "plain", "json"),
        default="auto",
        help="Formato output: auto usa rich se disponibile, altrimenti plain (default: auto)",
    )
    parser.add_argument("--pretty-json", action="store_true", help="Indenta l'output JSON")
    parser.add_argument("--schema-only", action="store_true", help="Mostra solo metadata e schema")
    parser.add_argument("--profile", action="store_true", help="Calcola qualita' e statistiche per colonna")
    parser.add_argument(
        "--profile-rows",
        type=int,
        default=0,
        help="Righe da usare per il profilo. Usa 0 per tutte (default: 0)",
    )
    parser.add_argument(
        "--top-values",
        type=int,
        default=3,
        help="Numero di valori piu' frequenti da mostrare nel profilo (default: 3)",
    )
    parser.add_argument("--search", help="Testo da cercare nelle colonne selezionate")
    parser.add_argument(
        "--search-limit",
        type=int,
        default=20,
        help="Numero massimo di righe trovate da mostrare (default: 20)",
    )
    parser.add_argument(
        "--search-rows",
        type=int,
        default=0,
        help="Numero massimo di righe da scansionare per la ricerca. Usa 0 per tutte (default: 0)",
    )
    parser.add_argument("--case-sensitive", action="store_true", help="Ricerca distinguendo maiuscole/minuscole")
    parser.add_argument("-b", "--browse", action="store_true", help="Apre una vista interattiva a colori navigabile")
    parser.add_argument(
        "--browse-rows",
        type=int,
        default=1000,
        help="Numero massimo di righe da caricare nel browser. Usa 0 per tutte (default: 1000)",
    )
    parser.add_argument("--no-color", action="store_true", help="Disabilita i colori ANSI")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.rows < 0:
        parser.error("--rows deve essere >= 0")
    if args.max_sample_columns < 0:
        parser.error("--max-sample-columns deve essere >= 0")
    if args.max_width < 5:
        parser.error("--max-width deve essere >= 5")
    if args.profile_rows < 0:
        parser.error("--profile-rows deve essere >= 0")
    if args.top_values < 0:
        parser.error("--top-values deve essere >= 0")
    if args.search_limit <= 0:
        parser.error("--search-limit deve essere > 0")
    if args.search_rows < 0:
        parser.error("--search-rows deve essere >= 0")
    if args.browse_rows < 0:
        parser.error("--browse-rows deve essere >= 0")
    if args.browse and args.schema_only:
        parser.error("--browse non puo' essere usato insieme a --schema-only")
    if args.schema_only and args.profile:
        parser.error("--profile non puo' essere usato insieme a --schema-only")
    if args.schema_only and args.search:
        parser.error("--search non puo' essere usato insieme a --schema-only")
    if args.browse and args.profile:
        parser.error("--profile non puo' essere usato insieme a --browse")
    if args.browse and args.search:
        parser.error("--search non puo' essere usato insieme a --browse")
    if args.browse and args.format == "json":
        parser.error("--format json non puo' essere usato insieme a --browse")

    args.color = enable_ansi(args.no_color)

    paths = expand_paths(args.files)
    if not paths:
        print("Nessun file trovato.", file=sys.stderr)
        return 1

    exit_code = 0
    seen: set[Path] = set()
    json_reports: list[dict[str, object]] = []
    for path in paths:
        normalized = Path(os.path.normpath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        file_exit_code, report = inspect_file(normalized, args)
        exit_code = max(exit_code, file_exit_code)
        if report is not None:
            json_reports.append(report)

    if args.format == "json" and json_reports:
        payload: object = json_reports[0] if len(json_reports) == 1 else json_reports
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty_json else None))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
