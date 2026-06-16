from __future__ import annotations

import html
import os
import subprocess
from pathlib import Path

import parquet_info as cli


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets" / "screenshots"
DEMO_FILE = Path("examples") / "demo_inventory.parquet"


COMMANDS: dict[str, list[str]] = {
    "overview": ["python", "parquet_info.py", str(DEMO_FILE), "--schema-only", "--format", "plain"],
    "profile": [
        "python",
        "parquet_info.py",
        str(DEMO_FILE),
        "--profile",
        "--profile-rows",
        "120",
        "--columns",
        "sku,product_name,warehouse,quantity,status,notes",
        "--format",
        "plain",
    ],
    "search": [
        "python",
        "parquet_info.py",
        str(DEMO_FILE),
        "--search",
        "priority",
        "--columns",
        "sku,product_name,warehouse,status,notes",
        "--format",
        "plain",
    ],
}


def run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def strip_ansi(text: str) -> str:
    return cli.ANSI_SEQUENCE.sub("", text).replace("\033[K", "").replace("\033[H", "").replace("\033[J", "")


def render_svg(title: str, content: str, destination: Path) -> None:
    lines = content.splitlines() or [""]
    width = min(1400, max(860, 28 + max(len(line) for line in lines) * 8))
    line_height = 24
    title_bar = 56
    padding = 28
    height = title_bar + padding * 2 + line_height * len(lines)
    text_y = title_bar + padding

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "  <defs>",
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#0f172a"/>',
        '      <stop offset="100%" stop-color="#111827"/>',
        "    </linearGradient>",
        '    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">',
        '      <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#020617" flood-opacity="0.35"/>',
        "    </filter>",
        "  </defs>",
        f'  <rect width="{width}" height="{height}" rx="22" fill="url(#bg)"/>',
        f'  <rect x="0" y="0" width="{width}" height="{title_bar}" rx="22" fill="#1f2937"/>',
        '  <circle cx="26" cy="28" r="7" fill="#fb7185"/>',
        '  <circle cx="50" cy="28" r="7" fill="#fbbf24"/>',
        '  <circle cx="74" cy="28" r="7" fill="#34d399"/>',
        f'  <text x="100" y="34" font-family="Segoe UI, Arial, sans-serif" font-size="20" fill="#e5e7eb">{html.escape(title)}</text>',
        f'  <g filter="url(#shadow)"><rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="18" fill="none" stroke="#334155"/></g>',
        f'  <text x="{padding}" y="{text_y}" font-family="Cascadia Mono, Consolas, monospace" font-size="18" fill="#d1d5db" xml:space="preserve">',
    ]

    for index, line in enumerate(lines):
        escaped = html.escape(line) or " "
        svg_lines.append(f'    <tspan x="{padding}" dy="{line_height if index else 0}">{escaped}</tspan>')

    svg_lines.extend(["  </text>", "</svg>"])
    destination.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")


def browser_snapshot() -> str:
    parquet_file = cli.pq.ParquetFile(ROOT / DEMO_FILE)
    sample_columns = ["sku", "product_name", "warehouse", "quantity", "status", "notes"]
    sample = cli.read_rows(parquet_file, 12, sample_columns)
    if sample is None:
        raise RuntimeError("Demo dataset does not contain rows for the browser screenshot.")

    browser = cli.TableBrowser(
        DEMO_FILE,
        sample,
        parquet_file.metadata,
        cli.Palette(False),
        max_width=22,
        loaded_rows_limit=12,
    )
    browser.selected_row = 3
    browser.selected_col = 4

    terminal_size = os.terminal_size((118, 18))
    original_get_terminal_size = cli.shutil.get_terminal_size
    cli.shutil.get_terminal_size = lambda fallback=(120, 32): terminal_size
    try:
        browser._ensure_visible()
        visible_columns = browser._visible_columns(terminal_size.columns)
        body_rows = browser._body_rows()
        loaded_rows = len(browser.rows)
        total_rows = browser.metadata.num_rows
        loaded_text = cli.format_number(loaded_rows)
        total_text = cli.format_number(total_rows)
        limit_note = ""
        if browser.loaded_rows_limit > 0 and loaded_rows < total_rows:
            limit_note = f"  sample: first {loaded_text} rows"

        lines = [
            browser.path.name,
            (
                f"rows {loaded_text}/{total_text}  "
                f"columns {len(browser.names)}  "
                f"row groups {browser.metadata.num_row_groups}"
                f"{limit_note}"
            ),
            browser._render_header(visible_columns, terminal_size.columns),
            browser._render_separator(visible_columns, terminal_size.columns),
        ]

        for display_row in range(body_rows):
            row_index = browser.row_offset + display_row
            if row_index >= loaded_rows:
                break
            lines.append(browser._render_row(row_index, visible_columns, terminal_size.columns))

        lines.append(browser._detail_line())
        lines.append("Arrows/WASD: move  PgUp/PgDn: rows  Home/End: columns  R: reset  Q/Esc: quit")
    finally:
        cli.shutil.get_terminal_size = original_get_terminal_size

    return "\n".join(strip_ansi(line).rstrip() for line in lines)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, command in COMMANDS.items():
        output = run_command(command)
        render_svg(f"parquet-info {name}", output, ASSETS_DIR / f"{name}.svg")
        print(f"Updated assets/screenshots/{name}.svg")
    render_svg("parquet-info browse", browser_snapshot(), ASSETS_DIR / "browse.svg")
    print("Updated assets/screenshots/browse.svg")


if __name__ == "__main__":
    main()
