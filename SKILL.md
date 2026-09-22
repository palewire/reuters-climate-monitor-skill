---
name: reuters-climate-paragraph
description: >
  Produce one publication-ready paragraph using the latest Reuters Climate
  Monitor data for the globe, a named region, or a latitude/longitude. Use
  when a newsroom user asks for today's climate-monitor temperature paragraph,
  a regional comparison with normal, or a location-specific reading.
compatibility: >
  Requires Python 3.11+, uv, and network access to the Reuters Climate Monitor
  CDN. The sidecar uses the Reuters feeds directly and does not scrape page
  text.
---

# Reuters Climate Monitor paragraph

Use the Python sidecar in this skill for every data lookup. Do not calculate
the anomaly from the daily and normal temperatures: use the published
`t2m_max_delta` field. Do not use a previous answer, a cached value, a
screenshot, or a legacy feed.

## Workflow

1. Identify the requested scope:
   - `global` for the whole globe.
   - `region` for a named aggregate such as Europe, Western Europe, or
     Southwest.
   - `location` for a point. Obtain latitude and longitude from a trusted
     geocoder or ask the user for coordinates. Never guess coordinates.
2. Resolve the date as the current UTC date. Pass it explicitly to the
   sidecar; this makes the result reproducible.
3. Ask for Celsius or Fahrenheit if the user did not specify a unit. Use
   Celsius when a default is required.
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
     --lat 48.8566 \
     --lng 2.3522 \
     --date YYYY-MM-DD \
     --unit celsius
   ```

5. Return the `paragraph` value exactly as the publication-ready copy. Then
   include the `site_url` and every URL in `source_urls` under a short
   **Verification** label. Keep the data date and resolved grid coordinates
   visible for a location result.
6. If the command fails because the requested date is not published, report
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

## Copy rules

The sidecar owns the wording and all number formatting. Do not rewrite the
paragraph into a stronger claim. In particular:

- “above” and “below” describe the published daily-high anomaly against the
  1961–1990 reference period.
- The daily high and anomaly are forecast/model values for the current monitor
  day; do not call them a weather-station observation.
- A point result represents the nearest 0.25-degree grid cell, not an entire
  city or administrative area.
- Keep the verification links with the draft. The Reuters page link lets an
  editor inspect the map; the CDN link lets an editor inspect the source feed
  or PMTiles object directly.

## Development and tests

From this skill directory:

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

The tests are offline and use synthetic feed and vector-tile responses. A
network smoke check is intentionally not part of the default test command.
