# Reuters Climate Monitor paragraph skill

This repository is a portable Claude Skill for producing one fixed,
publication-ready paragraph from a single published Reuters Climate Monitor
reading. Copy the repository folder into the Claude Desktop skills directory
or package it according to the newsroom's Claude deployment process.

The Python sidecar reads the Reuters Climate Monitor CDN, selects the requested
UTC date exactly, and emits JSON containing:

- one published daily high, normal, and anomaly;
- a fixed paragraph presenting those values;
- Celsius-to-Fahrenheit display conversion when requested;
- the Reuters page URL and direct CDN URL for verification; and
- resolved grid coordinates for point lookups.

The output does not produce rankings, multi-location averages, trends, records,
causes, climate attribution, or recomputed anomalies. Reuters Climate Monitor
data is used as published; the paragraph is only a fixed presentation layer.

## Use

The skill requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the
skill directory:

```bash
uv run climate-monitor generate \
  --scope global \
  --date YYYY-MM-DD \
  --unit celsius
```

For a named region:

```bash
uv run climate-monitor generate \
  --scope region \
  --region-set continent \
  --region Europe \
  --date YYYY-MM-DD \
  --unit celsius
```

For a location:

```bash
uv run climate-monitor generate \
  --scope location \
  --label "Paris" \
  --lat 48.8566 \
  --lng 2.3522 \
  --date YYYY-MM-DD \
  --unit celsius
```

See [SKILL.md](SKILL.md) for the Claude operating instructions and the
complete output policy.

## Development

Bootstrap the checkout and install all locked dependencies:

```bash
make bootstrap
```

Run the fast checks:

```bash
make check
```

Run the full local verification suite:

```bash
make verify
```

`make test` is offline and uses synthetic feed and vector-tile responses.
`make live-test` checks the current global, Europe, and Paris readings against
the published Reuters endpoints, plus a pinned historical Paris grid cell.
`make verify-fast` is the recommended fast local loop; `make verify` includes
the slower live checks. Network access is required for live data lookups and
package installation.

## Rights and attribution

The code in this repository is available under the MIT license. Reuters
Climate Monitor data, Reuters trademarks and branding, editorial copy, and
visual design are not included in that license. Use the live data feeds only
as permitted by their owners and keep Reuters attribution when required.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and
[CONTRIBUTING.md](CONTRIBUTING.md) for development guidance.
