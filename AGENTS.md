# Agent guide

## Purpose

This repository contains a Claude Skill and a Python sidecar that read one
published Reuters Climate Monitor value and format it for newsroom use.

The sidecar must remain source-first:

- select the requested UTC date exactly;
- use the published `t2m_max_delta` field;
- do not calculate new climate analysis;
- preserve the fixed output policy in `SKILL.md`; and
- keep direct Reuters verification URLs in every result.

Reuters data, trademarks, editorial copy, and visual design are not licensed
by this repository's MIT license.

## Layout

- `SKILL.md`: Claude operating instructions and output policy.
- `src/reuters_climate_paragraph/`: Click CLI and Reuters feed/tile client.
- `tests/`: Offline tests using synthetic feed and vector-tile responses.
- `Makefile`: Development, verification, and package commands.
- `.github/workflows/`: CI, CodeQL, and Scorecard workflows.

## Development

Use the template-based workflow:

```bash
make bootstrap
make check
make verify
```

`make check` runs diff, Ruff, formatting, ty, dependency, and workflow checks.
`make verify` also runs tests, package validation, and the wheel build.

Run focused commands when iterating:

```bash
make test
make type-check
make package-check PACKAGE=reuters_climate_paragraph
make coverage PACKAGE=reuters_climate_paragraph
```

Use `uv` for dependency changes and commit the resulting `uv.lock`. Keep the
package on the `src/` layout and retain the configured Ruff and ty checks.

## Releases

Versions come from Git tags through `setuptools-scm`; do not add a version
constant. Follow `RELEASING.md`. Creating tags, GitHub releases, and PyPI
publications requires explicit human approval.

## Changes

Update `SKILL.md` and `README.md` when the output policy or user-facing
behavior changes. Add a concise entry to the `Unreleased` section of
`CHANGELOG.md` for user-facing, compatibility, or security changes.
