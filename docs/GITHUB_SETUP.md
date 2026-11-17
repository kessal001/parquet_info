# GitHub Setup

Repository file hygiene is handled in this repo. These settings must be applied in GitHub itself.

## About

Use this description:

```text
Browse Parquet right in CMD with one command. Portable Windows EXE, interactive terminal viewer, schema, profiles, search and JSON. No data uploads.
```

Use this website after the first PyPI release:

```text
https://pypi.org/project/parquet-info/
```

## Topics

Add these topics:

```text
parquet
pyarrow
cli
terminal
data-engineering
analytics
python
apache-parquet
data-quality
developer-tools
parquet-viewer
windows
tui
```

## Features

Recommended repository settings:

- enable Issues;
- enable Discussions after the first external users arrive;
- enable Dependabot alerts;
- enable private vulnerability reporting;
- protect the default branch with the CI workflow required before merge.

## Release presentation

- Run the Windows workflow and verify the real binary before publishing a release.
- Attach the portable ZIP and SHA256SUMS.txt; state that the binary is unsigned.
- Lead the release with `parquet file.parquet`, a terminal screenshot, and the exact sample limits.
- Use the synthetic inventory demo in screenshots and issue reports; never attach business exports.
- Explain one concrete use case when sharing the project, such as checking a Power BI export without opening a notebook.
- Invite users to report unsupported Arrow types and performance issues. Do not promise a star count or manufacture engagement.
