"""Reuters newsroom paragraph rendering."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from .temperature import DEFAULT_TEMPERATURE_FORMATTER, TemperatureFormatter
from .urls import SITE_ROOT

if TYPE_CHECKING:
    from .models import Observation

CAUTION = (
    "Verify the date, place, and figures against the linked Reuters Climate "
    "Monitor before publication."
)


class ParagraphRenderer:
    """Render validated observations as deterministic newsroom copy.

    Args:
        temperature_formatter: Optional formatter for dependency injection.
        site_url: Reuters Climate Monitor URL included in the paragraph.

    Example:
        ``ParagraphRenderer().render(observation)["paragraph"]``
    """

    def __init__(
        self,
        temperature_formatter: TemperatureFormatter | None = None,
        site_url: str = SITE_ROOT,
    ) -> None:
        self._temperature_formatter = (
            temperature_formatter or DEFAULT_TEMPERATURE_FORMATTER
        )
        self._site_url = site_url

    def render(
        self,
        observation: Observation,
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Format an observation and render the fixed newsroom paragraph.

        Args:
            observation: Validated monitor observation.
            today: Optional UTC date used when rendering today's date in tests.

        Returns:
            A dictionary with display values, paragraph, and caution text.
        """
        direction = self._anomaly_direction(observation.anomaly_c)
        parsed_date = date.fromisoformat(observation.date)
        current_date = today or datetime.now(UTC).date()
        date_label = self._date_label(parsed_date, current_date)
        reading_verb = (
            "reached" if parsed_date < current_date else "is forecast to reach"
        )
        absolute_decimal_places = 1 if observation.scope in {"global", "region"} else 0
        daily_high = self._temperature_formatter.format_pair(
            observation.daily_high_c,
            absolute_decimal_places=absolute_decimal_places,
        )
        paragraph = (
            f"On {date_label}, {self._subject(observation)} {reading_verb} "
            f"{daily_high}, "
            "which is "
            f"{self._temperature_formatter.format_pair(observation.anomaly_c, anomaly=True)} "
            f"{direction} the 1961–1990 average, "
            f"according to the [Reuters Climate Monitor]({self._site_url})."
        )
        return {
            "daily_high": self._round_absolute(
                observation.daily_high_c,
                absolute_decimal_places,
            ),
            "normal_high": self._round_absolute(
                observation.normal_high_c,
                absolute_decimal_places,
            ),
            "anomaly": round(observation.anomaly_c, 1),
            "anomaly_direction": direction,
            "caution": CAUTION,
            "paragraph": paragraph,
        }

    @staticmethod
    def _anomaly_direction(value: float) -> str:
        """Return the editorial direction for an anomaly.

        Args:
            value: Published Celsius anomaly.

        Returns:
            ``above``, ``below``, or ``at``.
        """
        if value > 0:
            return "above"
        if value < 0:
            return "below"
        return "at"

    @staticmethod
    def _round_absolute(value: float, decimal_places: int) -> int | float:
        """Round an absolute value while preserving whole-degree integer output.

        Args:
            value: Absolute temperature in degrees Celsius.
            decimal_places: Number of decimal places to retain.

        Returns:
            An integer for whole-degree output or a float for decimal output.
        """
        if decimal_places == 0:
            return round(value)
        return round(value, decimal_places)

    @staticmethod
    def _date_label(parsed_date: date, current_date: date) -> str:
        """Format a current date as a weekday or a past date explicitly.

        Args:
            parsed_date: Observation date.
            current_date: Current UTC date.

        Returns:
            A weekday for today or a month-day-year label.
        """
        if parsed_date == current_date:
            return parsed_date.strftime("%A")
        return f"{parsed_date.strftime('%B')} {parsed_date.day}, {parsed_date.year}"

    @staticmethod
    def _subject(observation: Observation) -> str:
        """Build the subject phrase for an observation scope.

        Args:
            observation: Observation being rendered.

        Returns:
            The subject phrase used in the paragraph.
        """
        if observation.scope == "global":
            return "the global average high"
        if observation.scope == "region":
            return f"the average high in {observation.label}"
        return f"the high in {observation.label}"


def format_observation(
    observation: Observation,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Render an observation with the default paragraph renderer.

    Args:
        observation: Validated monitor observation.
        today: Optional UTC date used when rendering today's date in tests.

    Returns:
        A dictionary with display values, paragraph, and caution text.
    """
    return ParagraphRenderer().render(observation, today=today)
