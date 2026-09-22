"""Build a portable archive for the Reuters Climate Monitor Claude Skill."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL_DIRECTORY_NAME = "reuters-climate-paragraph"
SKILL_FILES = (
    ".python-version",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "SKILL.md",
    "pyproject.toml",
    "uv.lock",
)


def build_skill_archive(output_path: Path) -> None:
    """Build a Claude Skill archive containing runtime files.

    Args:
        output_path: Destination path for the zip archive.

    Raises:
        FileNotFoundError: If a required Skill file or source directory is
            missing.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary_directory:
        staging_root = Path(temporary_directory) / SKILL_DIRECTORY_NAME
        staging_root.mkdir()

        for relative_path in SKILL_FILES:
            source_path = ROOT / relative_path
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            shutil.copy2(source_path, staging_root / relative_path)

        source_directory = ROOT / "src"
        if not source_directory.is_dir():
            raise FileNotFoundError(source_directory)
        shutil.copytree(
            source_directory,
            staging_root / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
        )

        with zipfile.ZipFile(
            output_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in sorted(staging_root.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        path.relative_to(staging_root.parent),
                    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments containing the output path.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path for the Skill zip archive")
    return parser.parse_args()


def main() -> None:
    """Build the requested Skill archive."""
    arguments = parse_args()
    build_skill_archive(arguments.output)
    print(arguments.output)


if __name__ == "__main__":
    main()
