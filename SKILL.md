---
name: reuters-climate-paragraph
description: >
  Produce one fixed, publication-ready paragraph using one published Reuters
  Climate Monitor reading for the globe, a named region, or a
  latitude/longitude. Use when a newsroom user asks for today's climate-monitor
  temperature paragraph, a regional comparison with normal, or a
  location-specific reading.
compatibility: >
  Requires Python 3.11+, uv, and network access to the Reuters Climate Monitor
  CDN. The sidecar uses the Reuters feeds directly and does not scrape page
  text.
---

# Reuters Climate Monitor paragraph

Use the Python sidecar in this skill for every data lookup. It presents one
published reading in a fixed sentence with Celsius first and Fahrenheit in
parentheses, but it must not perform analysis. Do not calculate the anomaly from the daily and normal
temperatures: use the published `t2m_max_delta` field. Do not use a previous
answer, a cached value, a screenshot, or a legacy feed.

## Workflow

1. Identify the requested scope:
   - `global` for the whole globe.
   - `region` for a named aggregate such as Europe, Western Europe, or
     Southwest.
   - `location` for a named place. The sidecar uses the cached OpenStreetMap
     Nominatim service by default. Explicit user-provided coordinates may be
     passed instead; never guess coordinates.
2. Resolve the date as the current UTC date. Pass it explicitly to the
   sidecar; this makes the result reproducible.
3. Use the fixed Celsius-first, Fahrenheit-in-parentheses presentation. Do not
   ask the user to choose a unit.
4. Run the sidecar from this skill directory:

   ```bash
   uv run climate-monitor generate \
     --scope global \
     --date YYYY-MM-DD \
     --unit celsius
   ```

   For a continent:

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
     --date YYYY-MM-DD \
     --unit celsius
   ```

   Pass `--lat` and `--lng` together only when the user supplies coordinates
   or a trusted newsroom geocoder has already resolved the place.
5. Nominatim lookups are for occasional, user-triggered searches only. The
   sidecar identifies itself with a descriptive `User-Agent`, caches results,
   does not offer autocomplete or bulk geocoding, and sends only the place
   query. Do not send personal or confidential text. Follow the
   [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).
6. Return the `paragraph` value exactly as the publication-ready copy. Immediately
   after it, include the `caution` value. This caution should encourage the
   editor to verify the date, place, and figures before publication.
7. Under a short **Verification** label, always link `site_url` as the Reuters
   Climate Monitor. Include every URL in `source_urls`. For a geocoded
   location, also link `geocoder_url` so the editor can review the resolved
   point. Keep the data date and resolved grid coordinates visible for a
   location result.
8. If the command fails because the requested date is not published, report
   that plainly and do not substitute a different date. If a location is
   resolved to a nearby land grid cell, retain the sidecar's warning and
   resolved coordinates in the verification note.

## Supported regions

Use the exact display label and region-set pair:

| Region set       | Examples                                                                                                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| `continent`      | Africa, Asia, Australia, Europe, North America, South America                                                    |
| `western-europe` | Western Europe                                                                                                   |
| `us-contiguous`  | Contiguous United States                                                                                         |
| `ncei-climate`   | Northeast, Upper Midwest, Ohio Valley, Southeast, South, Southwest, Northern Rockies and Plains, Northwest, West |
| `country`        | A country published in the Western Europe country feed, such as France or Germany                                |

The sidecar rejects an unknown region instead of silently returning an
unfiltered feed.

## Allowed outputs

The sidecar may return only:

- the exact published date and one published reading;
- the published daily high, 1961–1990 normal, and `t2m_max_delta`;
- Celsius-first temperature pairs with the Fahrenheit equivalent in parentheses;
- fixed `above`, `below`, or `at` wording based only on the published anomaly's
  sign;
- the requested geography label and, for a point, the resolved monitor grid
  coordinates;
- Reuters page and direct CDN URLs for verification; and
- a caution directing editors to verify the result; and
- a geocoder review URL when a place name was geocoded; and
- the fixed paragraph generated by the sidecar.

Do not add rankings, averages across multiple rows, trends, records, causes,
climate attribution, severity labels, forecasts beyond the published daily
high, or any other custom analysis. Do not recompute or "correct" a published
value.

## Copy rules

The sidecar owns the wording and all number formatting. Do not rewrite the
paragraph into a stronger claim. In particular:

- “above” and “below” describe the published daily-high anomaly against the
  1961–1990 reference period.
- The daily high and anomaly are forecast/model values for the current monitor
  day; do not call them a weather-station observation.
- A point result represents the requested place's nearest 0.25-degree grid
  cell, not an entire city or administrative area. The paragraph may simply
  say “the high in [place]”; keep the resolved coordinates in the verification
  note.
- Preserve the paragraph's Markdown link on the Reuters Climate Monitor
  homepage.
- Keep the verification links with the draft. The Reuters page link lets an
  editor inspect the map; the CDN link lets an editor inspect the source feed
  or PMTiles object directly.

## Reuters style

### Temperature references

> Spell out *Celsius* or *Fahrenheit* on first reference with the word degrees. Do not use centigrade. Use figures except for zero and abbreviate to C and F on second reference. Write *86 degrees Fahrenheit (30 degrees Celsius)* on first reference and *86 F (30 C)* on second reference with a space between the numbers and letter. Spell out minus for clarity, as in *minus 10 C,* not -10 C. Note that temperatures are not hot or cold but high or low.

Always put Celsius first and the Fahrenheit equivalent in parentheses. For
example: `86 degrees Celsius (187 degrees Fahrenheit)` and `2.0 C (3.6 F)`.
Introduce the anomaly with “, which is” to give the two temperature statements
space in the sentence.

## Development and tests

From this skill directory:

```bash
uv run pytest -m "not integration"
uv run pytest -m integration
uv run ruff check .
uv run ty check
```

The default test command is offline and uses synthetic feed and vector-tile
responses. The integration command checks the current global, Europe, and
Paris readings against the published Reuters endpoints, plus a pinned
historical Paris grid cell.
