"""The `parquet` command: interactive browsing entirely inside the terminal."""
from __future__ import annotations

from pathlib import Path
import sys

from parquet_info import Palette, __version__, enable_ansi, main as cli_main, stringify_value


def choose_file(directory: Path, *, no_color: bool = False, force_color: bool = False) -> str | None:
    palette = Palette(enable_ansi(no_color, force_color))
    print(palette.paint(f"\n  PARQUET INFO  /  {__version__}", "1;36"))
    print("  Lettore interattivo nel terminale\n")
    try:
        files = sorted((path for path in directory.iterdir()
                        if path.is_file() and path.suffix.lower() in {".parquet", ".pq"}),
                       key=lambda path: path.name.casefold())[:20]
    except OSError:
        files = []
    if files:
        print(f"  File in {stringify_value(directory)}:\n")
        for index, path in enumerate(files, 1):
            print(f"  {index:2}. {stringify_value(path.name)}")
        print()
    print('  Incolla un percorso, anche con spazi. Invio per uscire.')
    try:
        choice = input("  File o numero: " if files else "  File: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not choice:
        return None
    if choice.isdecimal() and 1 <= int(choice) <= len(files):
        return str(files[int(choice) - 1])
    return choice.strip('"')


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments or set(arguments).issubset({"--color", "--no-color"}):
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("Uso: parquet FILE.parquet (richiede un terminale interattivo)", file=sys.stderr)
            return 2
        filename = choose_file(Path.cwd(), no_color="--no-color" in arguments, force_color="--color" in arguments)
        if not filename:
            return 0
        arguments = [filename, *arguments]
    report_options = {"--schema-only", "--profile", "--search", "--format", "--version", "--help", "-h", "-n", "--rows"}
    if not any(argument.split("=", 1)[0] in report_options for argument in arguments) and "--browse" not in arguments and "-b" not in arguments:
        arguments.append("--browse")
    try:
        return cli_main(arguments)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
