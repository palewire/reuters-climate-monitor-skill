"""Tests for Reuters-style temperature conversion and formatting."""

from reuters_climate_paragraph.temperature import TemperatureFormatter


def test_temperature_formatter_converts_celsius_to_fahrenheit() -> None:
    """The formatter converts Celsius values with the published formula."""
    formatter = TemperatureFormatter()

    assert formatter.celsius_to_fahrenheit(20) == 68
    assert formatter.celsius_to_fahrenheit(-10) == 14
    assert formatter.celsius_delta_to_fahrenheit(2) == 3.6


def test_temperature_formatter_formats_absolute_pairs() -> None:
    """Absolute values support whole degrees and one-decimal averages."""
    formatter = TemperatureFormatter()

    assert formatter.format_pair(20) == "20 degrees Celsius (68 degrees Fahrenheit)"
    assert (
        formatter.format_pair(-10.4)
        == "minus 10 degrees Celsius (13 degrees Fahrenheit)"
    )
    assert formatter.format_pair(0.2) == "zero degrees Celsius (32 degrees Fahrenheit)"
    assert (
        formatter.format_pair(20.04, absolute_decimal_places=1)
        == "20.0 degrees Celsius (68.1 degrees Fahrenheit)"
    )


def test_temperature_formatter_formats_anomaly_pairs_by_magnitude() -> None:
    """Anomalies use one decimal place and leave direction to the caller."""
    formatter = TemperatureFormatter()

    assert formatter.format_pair(2, anomaly=True) == "2.0 C (3.6 F)"
    assert formatter.format_pair(-2, anomaly=True) == "2.0 C (3.6 F)"
    assert formatter.format_pair(0, anomaly=True) == "zero C (zero F)"
