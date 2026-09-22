# Reuters Climate Paragraph Skill

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
uv run reuters-climate-paragraph generate \
  --scope global \
  --date YYYY-MM-DD \
  --unit celsius
```

For a named region:

```bash
uv run reuters-climate-paragraph generate \
  --scope region \
  --region-set continent \
  --region Europe \
  --date YYYY-MM-DD \
  --unit celsius
```

For a location:

```bash
uv run reuters-climate-paragraph generate \
  --scope location \
  --label "Paris" \
  --date YYYY-MM-DD \
  --unit celsius
```

The shorter `rcp` command is an alias for `reuters-climate-paragraph`.

## Result examples

The Skill returns one paragraph, a publication caution, and verification
links. The values below illustrate the response shapes; live values change as
new Reuters Climate Monitor data is published.

### Global reading

**Request:** “Give me today’s global Reuters Climate Monitor paragraph.”

> On Tuesday, the global average high is forecast to reach 20 degrees Celsius
> (68 degrees Fahrenheit), which is 1.2 C (2.2 F) above the 1961–1990 average,
> according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

**Caution:** Verify the date, place, and figures against the linked Reuters
Climate Monitor before publication.

**Verification:** The response includes the Reuters Climate Monitor page and
the direct global feed URL:
`https://graphics.thomsonreuters.com/newsapps_climate-forecast/daily-global-averages/latest-daily-averages.json`.

### Regional reading

**Request:** “Write today’s Reuters Climate Monitor paragraph for Europe.”

> On Tuesday, the average high in Europe is forecast to reach 20 degrees
> Celsius (68 degrees Fahrenheit), which is 3.5 C (6.3 F) above the 1961–1990
> average, according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

**Caution:** Verify the date, place, and figures against the linked Reuters
Climate Monitor before publication.

**Verification:** The response includes the Reuters Climate Monitor page and
the direct continent feed URL:
`https://graphics.thomsonreuters.com/newsapps_climate-forecast/region-sets/continent/latest-daily-averages.json`.

### Named location resolved with the default geocoder

**Request:** “Write today’s Reuters Climate Monitor paragraph for Swisher,
Iowa.”

> On Tuesday, the high in Swisher, Iowa is forecast to reach 21 degrees Celsius
> (70 degrees Fahrenheit), which is 1.1 C (2.0 F) above the 1961–1990 average,
> according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

**Caution:** Verify the date, place, and figures against the linked Reuters
Climate Monitor before publication.

**Verification:** The response includes the Reuters map query for the resolved
point, the direct PMTiles URL, the resolved grid coordinates
`(-91.75, 41.75)`, and an OpenStreetMap link where the geocoded point can be
reviewed:
<https://www.openstreetmap.org/?mlat=41.845622&mlon=-91.692970#map=12/41.845622/-91.692970>.

### Location supplied with explicit coordinates

**Request:** “Use latitude 48.8566 and longitude 2.3522 for Paris and write
today’s paragraph.”

> On Tuesday, the high in Paris is forecast to reach 27 degrees Celsius (81
> degrees Fahrenheit), which is 4.1 C (7.4 F) above the 1961–1990 average,
> according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

**Caution:** Verify the date, place, and figures against the linked Reuters
Climate Monitor before publication.

**Verification:** The response includes the Reuters map query for the supplied
point, the direct PMTiles URL, and the resolved monitor grid coordinates
`(2.25, 48.75)`. It does not include a geocoder URL because the coordinates
were supplied by the user.

### Historical-date reading

**Request:** “Give me the Reuters Climate Monitor paragraph for Paris on
2026-08-01.”

> On August 1, 2026, the high in Paris is forecast to reach 27 degrees Celsius
> (81 degrees Fahrenheit), which is 4.1 C (7.4 F) above the 1961–1990 average,
> according to the [Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).

**Caution:** Verify the date, place, and figures against the linked Reuters
Climate Monitor before publication.

**Verification:** The response keeps the requested date, shows the resolved
monitor grid coordinates, and links the exact dated PMTiles object. If that
date is not published, the Skill reports that plainly and does not substitute
today’s data.

### Custom analysis request

**Request:** “Which of these locations is hottest and what caused the
difference?”

**Response:** I can provide one published Reuters Climate Monitor reading for
one requested geography, but I cannot rank locations, explain causes, or add
custom analysis. Ask for a globe, region, or location reading instead.

## Package for Claude Desktop

Build the portable Skill archive with:

```bash
make skill-package
```

This creates `dist/reuters-climate-paragraph-skill.zip`. The archive contains
the root `SKILL.md`, the locked Python project, and the `src/` sidecar needed
for runtime lookups. Install or distribute the unzipped
`reuters-climate-paragraph/` folder using the newsroom's Claude Desktop Skill
deployment process. The Python wheel and source distribution created by
`make build` are separate developer artifacts and are not substitutes for the
Skill archive because they do not provide the root `SKILL.md`.

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
the published Reuters endpoints, plus a pinned historical Paris grid cell and
the geocoded Swisher, Iowa lookup. `make skill-test` checks the Skill metadata,
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

The code in this repository is available under the MIT license. Reuters
Climate Monitor data, Reuters trademarks and branding, editorial copy, and
visual design are not included in that license. Use the live data feeds only
as permitted by their owners and keep Reuters attribution when required.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and
[CONTRIBUTING.md](CONTRIBUTING.md) for development guidance.
