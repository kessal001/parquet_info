# Roadmap

`parquet-info` is meant to become the fastest first look at an unfamiliar Parquet file from a terminal.

## Near term

- Publish installable releases on PyPI.
- Broaden tests across common Arrow data types.
- Add performance benchmarks for large files and many columns.
- Improve terminal browsing on narrow and very wide terminals.

## Later

- Compare multiple Parquet files side by side.
- Detect suspicious quality patterns such as all-null columns, constant columns, and type drift.
- Add optional CSV/Markdown exports for profile summaries.
- Support directory-level dataset summaries.
