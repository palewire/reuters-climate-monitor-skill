# Contributing

Clone the repository. Move into the directory on your terminal.

Prepare the checkout and install dependencies for development.

```sh
make bootstrap
```

The command can be run in either the primary checkout or a linked worktree.
See the [README](README.md) for its environment-file behavior.

Install pre-commit to run a battery of automatic quick fixes against your work.

```sh
uv run pre-commit install
```

Run the fast, non-mutating checks.

```sh
make check
```

Run the complete local verification suite before opening a pull request.

```sh
make verify
```

Before releasing, review the package metadata, update `CHANGELOG.md`, and
follow the [release checklist](RELEASING.md).

## Releasing

Follow [RELEASING.md](RELEASING.md), including its post-merge GitHub Release
follow-up. The continuous deployment workflow publishes the package when the
exact version tag is pushed.
