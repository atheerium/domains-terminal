"""Utility functions for output and helpers.

MUST NOT depend on project modules (``domains_terminal.*``) to avoid circular imports.
Uses only the standard library.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".domains-terminal"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load user config from ``~/.domain-agent/config.json``."""
    path = CONFIG_DIR / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: Dict[str, Any]) -> None:
    """Persist user config to ``~/.domain-agent/config.json``."""
    _ensure_config_dir()
    path = CONFIG_DIR / "config.json"
    path.write_text(json.dumps(cfg, indent=2, default=str))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    """Configure logging with a simple stdout handler."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)-8s %(name)s  %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

# Colour codes (used only when output is a TTY)
_COLORS = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def _supports_color() -> bool:
    """Check if the terminal supports ANSI colour codes."""
    return sys.stdout.isatty() and bool(os.environ.get("TERM", "")) != "dumb"


def colorize(text: str, color: str) -> str:
    """Wrap *text* in ANSI colour codes if the terminal supports it."""
    if not _supports_color():
        return text
    code = _COLORS.get(color)
    if code is None:
        return text
    return f"{code}{text}{_COLORS['reset']}"


def format_output(
    data: List[Dict[str, Any]],
    fmt: str = "json",
    *,
    meta: Optional[Dict[str, Any]] = None,
    command: str = "",
    status: str = "ok",
    headers: Optional[List[str]] = None,
) -> str:
    """Format a list of records as JSON or a simple table.

    Parameters
    ----------
    data:
        List of record dicts to display.
    fmt:
        Output format — ``"json"`` (default) or ``"table"``.
    meta:
        Optional metadata dict included only in JSON output.
    command:
        The command name (included in JSON output).
    status:
        Result status (included in JSON output).
    headers:
        Column headers for table output.  When omitted, keys from the first
        non-empty record are used.

    Returns
    -------
    str
        Formatted string ready for stdout.
    """
    if fmt == "table":
        return _table_output(data, headers)
    return _json_output(data, command=command, meta=meta, status=status)


def _json_output(
    data: List[Dict[str, Any]],
    *,
    command: str = "",
    meta: Optional[Dict[str, Any]] = None,
    status: str = "ok",
) -> str:
    """Build a PipelineResult-like JSON structure and serialise it."""
    result: Dict[str, Any] = {
        "status": status,
        "command": command,
        "data": data,
        "meta": meta or {},
    }
    return json.dumps(result, indent=2, default=str)


def _table_output(
    data: List[Dict[str, Any]],
    headers: Optional[List[str]] = None,
) -> str:
    """Render *data* as a simple aligned text table.

    When *data* is empty, returns ``"<empty>"``.
    When *headers* is omitted, keys from the first record are used.
    """
    if not data:
        return "<empty>"

    if headers is None:
        headers = list(data[0].keys())

    # Build rows of string values
    rows: List[List[str]] = []
    for record in data:
        rows.append([str(record.get(h, "")) for h in headers])

    # Calculate column widths
    col_widths = [
        max(len(h), max((len(r[i]) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]

    # Build separator
    sep = "-+-".join("-" * w for w in col_widths)

    lines: List[str] = []

    # Header
    header_row = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    lines.append(header_row)
    lines.append(sep)

    # Data rows
    for row in rows:
        lines.append(" | ".join(cell.ljust(w) for cell, w in zip(row, col_widths)))

    return "\n".join(lines)


def confirm_action(prompt: str, default: bool = False) -> bool:
    """Ask the user a yes/no question on the terminal.

    Parameters
    ----------
    prompt:
        Question text (e.g. ``"Continue?"``).
    default:
        Default answer when the user presses Enter.

    Returns
    -------
    bool
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(f"{prompt}{suffix}").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.utcnow().isoformat()


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """Return *singular* or *plural* form based on *count*.

    ``pluralize(1, "domain")`` → ``"1 domain"``
    ``pluralize(3, "domain")`` → ``"3 domains"``
    """
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"
