"""Deterministic checks for the Claude Skill contract."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
SKILL_PATH = ROOT / "SKILL.md"
README_PATH = ROOT / "README.md"
PYPROJECT_PATH = ROOT / "pyproject.toml"
EVAL_CASES_PATH = ROOT / "tests" / "fixtures" / "skill_eval_cases.json"
PACKAGE_SCRIPT_PATH = ROOT / "scripts" / "package_skill.py"


def read_skill_parts() -> tuple[str, str]:
    """Read Skill frontmatter and instructions.

    Returns:
        A `(frontmatter, body)` pair.
    """
    content = SKILL_PATH.read_text()
    assert content.startswith("---\n")
    _, frontmatter, body = content.split("---\n", maxsplit=2)
    return frontmatter, body


def test_skill_metadata_has_required_discovery_fields() -> None:
    """Skill metadata describes what the Skill does and when to use it."""
    frontmatter, _ = read_skill_parts()

    assert "name: reuters-climate-paragraph" in frontmatter
    assert "description:" in frontmatter
    assert "Use when a newsroom user asks" in frontmatter
    assert "compatibility:" in frontmatter


def test_skill_instructions_define_the_output_contract() -> None:
    """Instructions require the paragraph, caution, and verification links."""
    _, body = read_skill_parts()

    required_phrases = (
        "current UTC date",
        "published `t2m_max_delta`",
        "Celsius first",
        "caution",
        "`site_url`",
        "`source_urls`",
        "`geocoder_url`",
        "Do not add rankings",
    )
    for phrase in required_phrases:
        assert phrase in body


def test_documented_commands_use_the_current_entrypoint() -> None:
    """README and Skill examples use the named CLI and its alias."""
    for path in (README_PATH, SKILL_PATH):
        content = path.read_text()
        assert "uv run climate-monitor" not in content
        assert "uv run reuters-climate-paragraph generate" in content
    assert "rcp" in README_PATH.read_text()


def test_package_exposes_primary_command_and_alias() -> None:
    """Packaging metadata exposes both supported console commands."""
    project = tomllib.loads(PYPROJECT_PATH.read_text())["project"]
    assert project["scripts"] == {
        "reuters-climate-paragraph": "reuters_climate_paragraph.cli:cli",
        "rcp": "reuters_climate_paragraph.cli:cli",
    }


def test_skill_package_script_includes_runtime_files() -> None:
    """The Skill archive includes instructions and the Python sidecar."""
    package_script = PACKAGE_SCRIPT_PATH.read_text()

    for required_path in ("SKILL.md", "pyproject.toml", "uv.lock", '"src"'):
        assert required_path in package_script


def test_skill_review_fixture_covers_required_request_types() -> None:
    """The human-review fixture covers allowed and refused request classes."""
    cases: list[dict[str, Any]] = json.loads(EVAL_CASES_PATH.read_text())
    by_id = {case["id"]: case for case in cases}
    required_ids = {
        "global-today",
        "region-europe",
        "location-nominatim",
        "location-explicit-coordinates",
        "historical-date",
        "custom-analysis",
    }

    assert set(by_id) == required_ids
    for case in cases:
        assert case["prompt"]
        assert case["expected_behavior"]
        assert case["must_include"]
        assert case["must_not_include"]
