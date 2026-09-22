# Reuters Climate Monitor paragraph skill

This repository is a portable Claude Skill for producing one fixed,
publication-ready paragraph from a single published Reuters Climate Monitor
reading. Copy the repository folder into the Claude Desktop skills directory
or package it according to the newsroom's Claude deployment process.

The Python sidecar reads the Reuters Climate Monitor CDN, selects the requested
UTC date exactly, and emits JSON containing:

- one published daily high, normal, and anomaly;
- a fixed paragraph presenting those values;
- Celsius-first temperature pairs with Fahrenheit in parentheses;
- the Reuters page URL and direct CDN URL for verification; and
- a publication caution and, for geocoded locations, a link to review the
  resolved point; and
- resolved grid coordinates for point lookups.

The output does not produce rankings, multi-location averages, trends, records,
causes, climate attribution, or recomputed anomalies. Reuters Climate Monitor
data is used as published; the paragraph is only a fixed presentation layer.

## Use

The skill requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the
skill directory:

```bash
uv run reuters-climate-monitor generate \
  --scope global \
  --date YYYY-MM-DD \
  --unit celsius
```

For a named region:

```bash
uv run reuters-climate-monitor generate \
  --scope region \
  --region-set continent \
  --region Europe \
  --date YYYY-MM-DD \
  --unit celsius
```

For a location:

```bash
uv run reuters-climate-monitor generate \
  --scope location \
  --label "Paris" \
  --date YYYY-MM-DD \
  --unit celsius
```

The shorter `rcm` command is an alias for `reuters-climate-monitor`.

Location names are geocoded with the cached OpenStreetMap Nominatim service by
default. Pass `--lat` and `--lng` together to use coordinates supplied by the
user instead. Nominatim is intended here for occasional, user-triggered
lookups: requests identify this application, repeated lookups are cached, and
the skill does not provide autocomplete or bulk geocoding. See the
[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

See [SKILL.md](SKILL.md) for the Claude operating instructions and the
complete output policy.

## Reuters style

### Temperature references

> Spell out *Celsius* or *Fahrenheit* on first reference with the word degrees. Do not use centigrade. Use figures except for zero and abbreviate to C and F on second reference. Write *86 degrees Fahrenheit (30 degrees Celsius)* on first reference and *86 F (30 C)* on second reference with a space between the numbers and letter. Spell out minus for clarity, as in *minus 10 C,* not -10 C. Note that temperatures are not hot or cold but high or low.

This skill always presents Celsius first and the Fahrenheit equivalent in
parentheses, such as `86 degrees Celsius (187 degrees Fahrenheit)`. Anomalies
follow the same order, such as `2.0 C (3.6 F)`, and the sentence introduces
the anomaly with “, which is”.

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
