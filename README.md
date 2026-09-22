A portable skill for AI assistants for producing a publication-ready paragraph
from the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

## Use with an AI assistant

The intended newsroom workflow is to ask the assistant for a paragraph in plain
language. The skill looks up the exact published Reuters Climate Monitor row
and returns only the ready-to-use paragraph.

### Global

**Input**

> Write today's Reuters Climate Monitor paragraph for the globe.

**Output**

> On Tuesday, the global average high is forecast to reach 20 degrees Celsius
> (68 degrees Fahrenheit), which is 1.2 C (2.2 F) above the 1961–1990 average,
> according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

### Region

**Input**

> Write today's Reuters Climate Monitor paragraph for Europe.

**Output**

> On Tuesday, the average high in Europe is forecast to reach 18 degrees
> Celsius (65 degrees Fahrenheit), which is 3.4 C (6.0 F) above the 1961–1990
> average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

### Location

**Input**

> Write the Reuters Climate Monitor paragraph for Paris on Aug. 1, 2026. Do
> not use latitude or longitude; resolve the place name.

**Output**

> On August 1, 2026, the high in Paris reached 28 degrees Celsius (83 degrees
> Fahrenheit), which is 5.3 C (9.5 F) above the 1961–1990 average, according
> to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

## Use from the CLI

The skill requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the
skill directory:

The sidecar does not need a `.env` file or secrets. If your shell or Desktop
installation sets `UV_ENV_FILE` globally, clear it before each `uv` command:

```bash
env -u UV_ENV_FILE uv run ...
```

To list every region set and label currently published by the Monitor:

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph regions
```

To list labels from one region set:

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph regions \
  --region-set continent
```

These commands return JSON and read the current public feeds, so they are the
best source when a user asks which regions are supported.

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
  --scope global \
  --date YYYY-MM-DD
```

For a named region:

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
  --scope region \
  --region-set continent \
  --region Europe \
  --date YYYY-MM-DD
```

For a location:

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
  --scope location \
  --label "Paris" \
  --date YYYY-MM-DD
```

The shorter `rcp` command is an alias for `reuters-climate-paragraph`.

## Diagnose network failures

Add `--verbose` before the command to print request status, exception details,
and safe CDN response headers to stderr without changing the JSON output:

```bash
env -u UV_ENV_FILE uv run reuters-climate-paragraph --verbose generate \
  --scope global \
  --date YYYY-MM-DD
```

The diagnostics do not include response bodies or query strings. They can show
whether a request reached the CDN, which HTTP status it returned, and whether
the response came from a proxy or content-delivery firewall.

## CLI example output

The CLI prints JSON containing the published values, the ready-to-use
paragraph, and links for verification. The same global example above produces:

```console
$ env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
    --scope global \
    --date 2026-09-22
{
  "anomaly": 1.2,
  "anomaly_c": 1.234,
  "anomaly_direction": "above",
  "caution": "Verify the date, place, and figures against the linked Reuters Climate Monitor before publication.",
  "coordinates": null,
  "daily_high": 20,
  "daily_high_c": 20.04,
  "date": "2026-09-22",
  "geocoder_url": null,
  "label": "the globe",
  "land_swapped": false,
  "normal_high": 19,
  "normal_high_c": 18.99,
  "paragraph": "On Tuesday, the global average high is forecast to reach 20 degrees Celsius (68 degrees Fahrenheit), which is 1.2 C (2.2 F) above the 1961\u20131990 average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).",
  "scope": "global",
  "site_url": "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/"
}
```

The regional example produces:

```console
$ env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
    --scope region \
    --region-set continent \
    --region Europe \
    --date 2026-09-22
{
  "anomaly": 3.4,
  "anomaly_c": 3.36,
  "anomaly_direction": "above",
  "caution": "Verify the date, place, and figures against the linked Reuters Climate Monitor before publication.",
  "coordinates": null,
  "daily_high": 18,
  "daily_high_c": 18.12,
  "date": "2026-09-22",
  "geocoder_url": null,
  "label": "Europe",
  "land_swapped": false,
  "normal_high": 15,
  "normal_high_c": 14.76,
  "paragraph": "On Tuesday, the average high in Europe is forecast to reach 18 degrees Celsius (65 degrees Fahrenheit), which is 3.4 C (6.0 F) above the 1961\u20131990 average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).",
  "scope": "region",
  "site_url": "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/"
}
```

Location requests can omit coordinates. In that case, the sidecar geocodes the
place name and includes the geocoder link in its verification details:

```console
$ env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
    --scope location \
    --label "Paris" \
    --date 2026-08-01
{
  "anomaly": 5.3,
  "anomaly_c": 5.3,
  "anomaly_direction": "above",
  "caution": "Verify the date, place, and figures against the linked Reuters Climate Monitor before publication.",
  "coordinates": [
    2.25,
    48.75
  ],
  "daily_high": 28,
  "daily_high_c": 28.200001,
  "date": "2026-08-01",
  "geocoder_url": "https://www.openstreetmap.org/?mlat=48.853495&mlon=2.348391#map=12/48.853495/2.348391",
  "label": "Paris",
  "land_swapped": false,
  "normal_high": 23,
  "normal_high_c": 22.9,
  "paragraph": "On August 1, 2026, the high in Paris reached 28 degrees Celsius (83 degrees Fahrenheit), which is 5.3 C (9.5 F) above the 1961\u20131990 average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).",
  "scope": "location",
  "site_url": "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/?lat=48.8535&lng=2.3484&zoom=6&place=Paris"
}
```

When a user has already identified the place with coordinates, pass them
directly instead:

```console
$ env -u UV_ENV_FILE uv run reuters-climate-paragraph generate \
    --scope location \
    --label "Paris" \
    --lat 48.8566 \
    --lng 2.3522 \
    --date 2026-08-01
{
  "anomaly": 5.3,
  "anomaly_c": 5.3,
  "anomaly_direction": "above",
  "caution": "Verify the date, place, and figures against the linked Reuters Climate Monitor before publication.",
  "coordinates": [
    2.25,
    48.75
  ],
  "daily_high": 28,
  "daily_high_c": 28.2,
  "date": "2026-08-01",
  "geocoder_url": null,
  "label": "Paris",
  "land_swapped": false,
  "normal_high": 23,
  "normal_high_c": 22.9,
  "paragraph": "On August 1, 2026, the high in Paris reached 28 degrees Celsius (83 degrees Fahrenheit), which is 5.3 C (9.5 F) above the 1961\u20131990 average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).",
  "scope": "location",
  "site_url": "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/?lat=48.8566&lng=2.3522&zoom=6&place=Paris",
}
```

The values above are examples of the output shape; the CLI always fetches the
requested date from the published feeds.

## Install the Python package

The Python sidecar is also distributed as a standard package on PyPI. After a
release, install the CLI into a tool environment with:

```bash
uv tool install reuters-climate-paragraph
```

For a one-off command without installing it permanently:

```bash
uvx reuters-climate-paragraph generate \
  --scope global \
  --date YYYY-MM-DD
```

The PyPI package provides the Python library and CLI only. It does not include
the root `SKILL.md`, so use the [portable Skill archive](#package-for-claude-desktop)
when installing the complete Claude Desktop Skill.

## Package for Claude Desktop

Build the portable Skill archive with:

```bash
make skill-package
```

This creates `dist/reuters-climate-paragraph.skill`. The archive contains
the root `SKILL.md`, the locked Python project, and the `src/` sidecar needed
for runtime lookups. Install or distribute the unzipped
`reuters-climate-paragraph/` folder using the newsroom's Claude Desktop Skill
deployment process. The Python wheel and source distribution created by
`make build` are separate developer artifacts and are not substitutes for the
Skill archive because they do not provide the root `SKILL.md`.

Tagged releases publish this same `.skill` archive as an asset on the GitHub
Release page alongside the PyPI package.

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

> Spell out _Celsius_ or _Fahrenheit_ on first reference with the word degrees. Do not use centigrade. Use figures except for zero and abbreviate to C and F on second reference. Write _86 degrees Fahrenheit (30 degrees Celsius)_ on first reference and _86 F (30 C)_ on second reference with a space between the numbers and letter. Spell out minus for clarity, as in _minus 10 C,_ not -10 C. Note that temperatures are not hot or cold but high or low.

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
the published [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/)
endpoints, plus a pinned historical Paris grid cell and the geocoded Swisher,
Iowa lookup. `make skill-test` checks the Skill metadata,
instructions, review cases, and both CLI entrypoints.
`make verify-fast` is the recommended fast local loop; `make verify` includes
the slower live checks. Network access is required for live data lookups and
package installation.

The human-review prompts are listed in
`tests/fixtures/skill_eval_cases.json`. Run them in the target Claude Desktop
installation when changing `SKILL.md`; check that each response follows its
`expected_behavior`, includes every `must_include` item, and avoids every
`must_not_include` item.

## Rights and attribution

The code in this repository is available under the MIT license. [Reuters
Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/)
data, Reuters trademarks and branding, editorial copy, and visual design are
not included in that license. Use the live data feeds only
as permitted by their owners and keep Reuters attribution.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and
[CONTRIBUTING.md](CONTRIBUTING.md) for development guidance.
