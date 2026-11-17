# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog, and this project uses semantic versioning.

## [Unreleased]

## [0.2.0] - 2026-11-17

### Added

- `parquet` command: interactive browsing by default, terminal file selection when launched without a file.
- Live `/` filtering of loaded rows, preserving original row numbers; C clears the filter.
- Portable Windows executable, app icon, user PATH installer/remover, and Windows build workflow.
- Regression coverage for command dispatch, terminal selection, filtering and navigation.

### Changed

- Browse mode now returns an error when no interactive terminal is available.
- Existing `parquet-info` reporting commands remain available.
- Refreshed terminal colors, selection highlight and compact keyboard help.
- `--color` forces colored text; `--no-color` disables it.
- Control characters in data are displayed as escaped text.

## Previous unreleased changes

### Added

- MIT license and public contribution documents.
- Automated test coverage for core CLI behavior.
- GitHub Actions workflows for CI and release publishing.

### Changed

- Public repo hygiene now excludes local/generated artifacts and private parquet exports.

## [0.1.0] - 2026-06-16

### Added

- Initial `parquet-info` CLI.
- Schema inspection, row preview, JSON export, text search, column profiling, and interactive terminal browsing.
- Demo parquet dataset and generated README screenshots.
