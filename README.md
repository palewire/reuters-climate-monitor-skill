# Reuters Climate Monitor paragraph skill

This repository is a portable Claude Skill. Copy the repository folder into
the Claude Desktop skills directory or package it according to the newsroom's
Claude deployment process.

The sidecar is deliberately source-first: it reads the Reuters Climate Monitor
CDN, selects the requested UTC date exactly, and emits JSON containing:

- a deterministic publication-ready paragraph;
- the source date and Celsius values;
- the Reuters page URL;
- direct feed or PMTiles URLs for verification;
- the resolved grid coordinates for point lookups.

Install and test it with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ty check
```

## Rights and attribution

The code in this repository is available under the MIT license. Reuters
Climate Monitor data, Reuters trademarks and branding, editorial copy, and
visual design are not included in that license. Use the live data feeds only
as permitted by their owners and keep Reuters attribution when required.
