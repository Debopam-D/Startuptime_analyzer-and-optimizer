"""Output formatting utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def format_table_row(values: list[str], widths: list[int]) -> str:
    """Format a table row with fixed column widths."""
    return " | ".join(f"{v:<{w}}" for v, w in zip(values, widths))


def calculate_column_widths(rows: list[list[str]]) -> list[int]:
    """Calculate optimal column widths for a table."""
    if not rows:
        return []

    num_cols = len(rows[0])
    widths = [0] * num_cols

    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    return widths


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple formatted table."""
    all_rows = [headers] + rows
    widths = calculate_column_widths(all_rows)

    # Header
    print(format_table_row(headers, widths))
    print("-" * sum(w + 3 for w in widths))

    # Rows
    for row in rows:
        print(format_table_row(row, widths))


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """Format a percentage value with sign."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimal_places}f}%"


def format_improvement(baseline: float, optimized: float, higher_is_better: bool = False) -> str:
    """Format improvement percentage with color indication."""
    if baseline == 0:
        return "N/A"

    pct = ((baseline - optimized) / baseline) * 100

    if higher_is_better:
        pct = -pct

    if pct > 0:
        return f"🟢 {pct:+.1f}%"
    if pct < 0:
        return f"🔴 {pct:+.1f}%"
    return f"⚪ {pct:+.1f}%"


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return singular or plural form based on count."""
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"