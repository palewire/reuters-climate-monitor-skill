"""Temperature conversion and Reuters-style display formatting."""

from __future__ import annotations


class TemperatureFormatter:
    """Convert Celsius values and format newsroom temperature text.

    Example:
        ``TemperatureFormatter().format_pair(20)`` returns the Celsius-first
        display used in generated paragraphs.
    """

    @staticmethod
    def celsius_to_fahrenheit(value_c: float) -> float:
        """Convert a Celsius temperature to Fahrenheit.

        Args:
            value_c: Temperature in degrees Celsius.

        Returns:
            The equivalent temperature in degrees Fahrenheit.

        Example:
            ``TemperatureFormatter.celsius_to_fahrenheit(20) == 68``
        """
        return value_c * 9 / 5 + 32

    @staticmethod
    def celsius_delta_to_fahrenheit(value_c: float) -> float:
        """Convert a Celsius difference to a Fahrenheit difference.

        Args:
            value_c: Temperature difference in degrees Celsius.

        Returns:
            The equivalent temperature difference in degrees Fahrenheit.

        Example:
            ``TemperatureFormatter.celsius_delta_to_fahrenheit(2) == 3.6``
        """
        return value_c * 9 / 5

    @staticmethod
    def format_absolute(
        value: float,
        unit_name: str,
        *,
        decimal_places: int = 0,
    ) -> str:
        """Format an absolute temperature using Reuters style.

        Args:
            value: Absolute temperature in the selected display unit.
            unit_name: Full unit name, either ``Celsius`` or ``Fahrenheit``.
            decimal_places: Number of decimal places for nonzero values.

        Returns:
            A temperature with ``degrees`` and a clear minus sign.

        Example:
            ``TemperatureFormatter().format_absolute(-10.4, "Celsius")`` returns
            ``"minus 10 degrees Celsius"``.
        """
        rounded = round(value, decimal_places)
        if rounded == 0:
            number = "zero"
        elif rounded < 0:
            number = f"minus {abs(rounded):.{decimal_places}f}"
        else:
            number = f"{rounded:.{decimal_places}f}"
        if decimal_places == 0:
            number = number.replace(".0", "")
        return f"{number} degrees {unit_name}"

    @staticmethod
    def format_anomaly(value: float, unit_abbreviation: str) -> str:
        """Format an anomaly using Reuters style.

        Args:
            value: Anomaly temperature in the selected display unit.
            unit_abbreviation: Unit abbreviation, either ``C`` or ``F``.

        Returns:
            A one-decimal absolute anomaly with a space before its unit
            abbreviation.

        Example:
            ``TemperatureFormatter().format_anomaly(-2, "C")`` returns
            ``"2.0 C"``.
        """
        rounded = round(abs(value), 1)
        number = "zero" if rounded == 0 else f"{rounded:.1f}"
        return f"{number} {unit_abbreviation}"

    def format_pair(
        self,
        value_c: float,
        *,
        anomaly: bool = False,
        absolute_decimal_places: int = 0,
    ) -> str:
        """Format Celsius first with the Fahrenheit equivalent in parentheses.

        Args:
            value_c: Temperature in degrees Celsius.
            anomaly: Whether to format the value as a one-decimal anomaly.
            absolute_decimal_places: Decimal places for non-anomaly values.

        Returns:
            A Reuters-style Celsius/Fahrenheit temperature pair.

        Example:
            ``TemperatureFormatter().format_pair(20)`` returns
            ``"20 degrees Celsius (68 degrees Fahrenheit)"``.
        """
        value_f = self.celsius_to_fahrenheit(value_c)
        if anomaly:
            celsius = self.format_anomaly(value_c, "C")
            fahrenheit = self.format_anomaly(
                self.celsius_delta_to_fahrenheit(value_c), "F"
            )
        else:
            celsius = self.format_absolute(
                value_c,
                "Celsius",
                decimal_places=absolute_decimal_places,
            )
            fahrenheit = self.format_absolute(
                value_f,
                "Fahrenheit",
                decimal_places=absolute_decimal_places,
            )
        return f"{celsius} ({fahrenheit})"


DEFAULT_TEMPERATURE_FORMATTER = TemperatureFormatter()


def format_absolute_temperature(
    value: float,
    unit_name: str,
    *,
    decimal_places: int = 0,
) -> str:
    """Format an absolute temperature with the default formatter.

    Args:
        value: Absolute temperature in the selected display unit.
        unit_name: Full unit name, either ``Celsius`` or ``Fahrenheit``.
        decimal_places: Number of decimal places for nonzero values.

    Returns:
        A Reuters-style absolute temperature.

    Example:
        ``format_absolute_temperature(20, "Celsius")`` returns
        ``"20 degrees Celsius"``.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_absolute(
        value,
        unit_name,
        decimal_places=decimal_places,
    )


def format_anomaly_temperature(value: float, unit_abbreviation: str) -> str:
    """Format an anomaly with the default formatter.

    Args:
        value: Anomaly temperature in the selected display unit.
        unit_abbreviation: Unit abbreviation, either ``C`` or ``F``.

    Returns:
        A Reuters-style one-decimal anomaly.

    Example:
        ``format_anomaly_temperature(2, "C")`` returns ``"2.0 C"``.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_anomaly(value, unit_abbreviation)


def format_temperature_pair(
    value_c: float,
    *,
    anomaly: bool = False,
    absolute_decimal_places: int = 0,
) -> str:
    """Format a Celsius/Fahrenheit pair with the default formatter.

    Args:
        value_c: Temperature in degrees Celsius.
        anomaly: Whether to format the value as a one-decimal anomaly.
        absolute_decimal_places: Decimal places for non-anomaly values.

    Returns:
        A Reuters-style Celsius-first temperature pair.

    Example:
        ``format_temperature_pair(20)`` returns
        ``"20 degrees Celsius (68 degrees Fahrenheit)"``.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_pair(
        value_c,
        anomaly=anomaly,
        absolute_decimal_places=absolute_decimal_places,
    )
