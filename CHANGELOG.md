# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Publish the Python sidecar and CLI as a standard PyPI package alongside the
  portable Claude Desktop Skill archive.
- Attach the portable `.skill` archive to the GitHub Release created for each
  tagged package release.
- Add a `regions` command that lists the region sets and labels currently
  published by the Reuters Climate Monitor.

### Changed

- Remove the unnecessary unit option; output is always the fixed Celsius-first
  format with Fahrenheit in parentheses.
- Show one decimal place for global and regional average temperatures while
  keeping local grid-square temperatures rounded to whole degrees.
- Keep raw feed and tile URLs internal instead of returning them in JSON.
- Format paragraph temperatures with Celsius first and the Fahrenheit
  equivalent in parentheses.
- Route past point lookups to the published ERA5 anomaly map and keep current
  and future point lookups on HRES.
- Use past tense for published historical ERA5 point readings instead of
  forecast wording.
- Use the cached OpenStreetMap Nominatim service to geocode named locations by
  default.

### Fixed

- Clear inherited `UV_ENV_FILE` settings before Skill `uv` commands so a
  missing project-local `.env` file does not block the packaged sidecar.

### Removed

### Security
