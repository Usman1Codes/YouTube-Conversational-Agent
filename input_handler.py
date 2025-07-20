#!/usr/bin/env python3
"""input_handler.py
Module 1: Robust CLI input parsing & YouTube link validation.

Responsibilities
----------------
1. Parse command-line arguments for the CLI tool.
2. Validate that the supplied argument is a valid YouTube URL *or* raw video ID.
3. Extract and return the canonical 11-character YouTube video ID.
4. Optionally verify that the video exists and is accessible via the YouTube Data API when an API key is available.

The goal is to centralise all input-related logic so that the rest of the codebase can simply call
    >>> video_id = parse_and_validate()

and get a rock-solid video ID or an explanatory exception.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,
)

# ────────────────────────────────────────────────────────────────────────────────
# Constants & Regex helpers
# ────────────────────────────────────────────────────────────────────────────────

YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# Regex loosely adapted from YouTube URL specifications.
YOUTUBE_URL_PATTERN = re.compile(
    r"""
    ^(?:https?://)?                              # optional scheme
    (?:www\.)?                                  # optional www.
    (?:                                          # host alternatives
        youtu\.be/                               #   youtu.be/<id>
      | youtube\.com/                            #   youtube.com/<paths>
        (?:                                      #   various path formats
            (?:embed|v|shorts)/
          | .*?watch\?.*?v=                      #   watch?v=<id>
        )
    )
    (?P<id>[a-zA-Z0-9_-]{11})                    # final capture group of video id
    (?:[&?].*)?$                                 # allow extra query params
    """,
    re.X,
)

API_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


# ────────────────────────────────────────────────────────────────────────────────
# Dataclass for parsed CLI config
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class CliConfig:
    """Container for the configuration produced by parse_cli_args()."""

    raw_input: str
    video_id: str
    api_key: Optional[str]
    debug: bool = False


# ────────────────────────────────────────────────────────────────────────────────
# Exceptions
# ────────────────────────────────────────────────────────────────────────────────


class InvalidYouTubeLinkError(ValueError):
    """Raised when the provided link cannot be parsed into a valid video ID."""


class InaccessibleVideoError(RuntimeError):
    """Raised when the YouTube Data API indicates the video does not exist or is private."""


# ────────────────────────────────────────────────────────────────────────────────
# Core public helpers
# ────────────────────────────────────────────────────────────────────────────────


def parse_cli_args(argv: list[str] | None = None) -> CliConfig:  # pragma: no cover
    """Parse CLI arguments and return a `CliConfig` object.

    Parameters
    ----------
    argv
        Pass `None` to default to *sys.argv[1:]* (standard behaviour for
        `argparse`).
    """

    parser = argparse.ArgumentParser(
        description="Summarise YouTube videos from your terminal.",
        prog="yt",
    )
    parser.add_argument("url", help="A YouTube video URL or the 11-character video ID.")
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=os.getenv("YOUTUBE_DATA_API_KEY"),
        help="YouTube Data API key (overrides YOUTUBE_DATA_API_KEY env variable).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable verbose debug logging.",
    )

    ns = parser.parse_args(argv)

    # Configure logging level as early as possible.
    if ns.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    logger.debug("Raw CLI input: %s", ns.url)

    video_id = _extract_video_id(ns.url)

    # If user provided an API key, verify the video is accessible.
    if ns.api_key:
        logger.debug("Verifying video accessibility via YouTube Data API…")
        _verify_video_exists(video_id, ns.api_key)
    else:
        logger.debug("No YouTube Data API key supplied – skipping remote video verification.")

    return CliConfig(
        raw_input=ns.url,
        video_id=video_id,
        api_key=ns.api_key,
        debug=ns.debug,
    )


# ────────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────────


def _extract_video_id(user_input: str) -> str:
    """Return an 11-character YouTube video ID from various input formats.

    Accepts full URLs (with any typical YouTube host variations) **or** a raw
    11-character video ID.
    """

    # Case 1 – user already passed a raw video ID.
    if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(user_input):
        logger.debug("Input recognised as raw video ID.")
        return user_input

    # Case 2 – attempt to parse as URL.
    # Fast path via regex: this works for the vast majority of cases and avoids
    # additional machinery.
    url_match = YOUTUBE_URL_PATTERN.match(user_input)
    if url_match:
        video_id = url_match.group("id")
        logger.debug("Extracted video ID via regex: %s", video_id)
        return video_id

    # Slow path – fall back to urllib.parse for exotic links.
    try:
        parsed = urlparse(user_input)
        qs = parse_qs(parsed.query)
        if "v" in qs and YOUTUBE_VIDEO_ID_PATTERN.fullmatch(qs["v"][0]):
            logger.debug("Extracted video ID via querystring parse: %s", qs["v"][0])
            return qs["v"][0]
    except Exception as exc:  # pragma: no cover – extremely unlikely
        logger.debug("urllib.parse failed to interpret input: %s", exc)

    raise InvalidYouTubeLinkError(
        f"Unable to extract a valid YouTube video ID from input: '{user_input}'."
    )


def _verify_video_exists(video_id: str, api_key: str) -> None:
    """Raise `InaccessibleVideoError` if the video does not exist or is private."""

    import requests  # imported lazily to avoid mandatory dependency when not verifying

    params = {
        "id": video_id,
        "part": "status",
        "key": api_key,
    }

    try:
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get("items"):
            raise InaccessibleVideoError(f"Video ID '{video_id}' does not exist or is private.")
    except requests.RequestException as exc:
        # If the request fails, we log a warning but do NOT block execution; the
        # transcript-fetching stage will be the ultimate judge. This design choice
        # ensures the CLI remains usable even if the API quota is exhausted.
        logger.warning("YouTube Data API call failed (%s). Continuing without remote validation.", exc)


# ────────────────────────────────────────────────────────────────────────────────
# Convenience entry point
# ────────────────────────────────────────────────────────────────────────────────


def get_video_id_from_cli(argv: list[str] | None = None) -> str:  # pragma: no cover
    """Shorthand helper used by external modules (e.g. cli.py)."""

    cfg = parse_cli_args(argv)
    return cfg.video_id 