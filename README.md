# Reuters Climate Monitor paragraph skill

This folder is a portable Claude Skill. Copy the complete folder into the
Claude Desktop skills directory or package it according to the newsroom's
Claude deployment process.

The sidecar is deliberately source-first: it reads the Reuters Climate Monitor
CDN, selects the requested UTC date exactly, and emits JSON containing:

- a deterministic publication-ready paragraph;
- the source date and Celsius values;
- the Reuters page URL;
- direct feed or PMTiles URLs for verification;
- the resolved grid coordinates for point lookups.

The output is intentionally limited to one published reading. The paragraph
is a fixed presentation of that reading, and Fahrenheit is a display
conversion from the published Celsius values. The skill does not produce
rankings, multi-location averages, trends, records, causes, climate
attribution, or recomputed anomalies.

Install and test it with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ty check
```
