#!/usr/bin/env python3
"""yt_cli.py - Entry point `yt <link>`

This small wrapper wires together Module 1 (*input_handler*) and Module 2
(*video_extractor*). Additional functionality (summarisation, QA, etc.) can be
layered on later without touching the hardened foundation.
"""

from __future__ import annotations

import sys

from pytubefix import YouTube

from input_handler import parse_cli_args
from video_extractor import extract_text_from_video
from gemini_helpers import make_summary, make_description, start_chat_loop

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env (first look in script directory, then default search)
script_dir = Path(__file__).resolve().parent
dotenv_path = script_dir / ".env"
load_dotenv(dotenv_path if dotenv_path.exists() else None)
# Fallback: also attempt to load .env from the current working directory tree
load_dotenv()  # uses default search (pwd → parents)


def _fetch_title(video_url: str) -> str | None:
    """Lightweight wrapper around pytubefix to obtain the video title."""
    try:
        yt = YouTube(video_url)
        return yt.title
    except Exception:
        return None


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    cfg = parse_cli_args(None if argv is None else argv)

    # Try to fetch title (optional)
    title = _fetch_title(cfg.raw_input) or "Untitled Video"

    print("→ Fetching transcript …", flush=True)
    transcript = extract_text_from_video(cfg.video_id, cfg.raw_input)

    if not transcript:
        print("✖ Failed to obtain text from the specified video.")
        sys.exit(1)

    # Ask user which output they want
    print("\nChoose an option:")
    print("1. Summary (concise bullet-point analysis)")
    print("2. Detailed description with interactive Q&A")

    choice = input("Enter 1 or 2: ").strip()
    while choice not in {"1", "2"}:
        choice = input("Please enter 1 or 2: ").strip()

    api_key = os.getenv("GEMINI_API_KEY")
    # Temporary debug print to verify the key being used.
    print(f"\n[DEBUG] Using API Key: {api_key[:5]}...{api_key[-4:] if api_key else 'Not Found'}\n")
    if not api_key:
        print("✖ GEMINI_API_KEY environment variable is missing.")
        sys.exit(1)

    if choice == "1":
        print("\nGenerating summary …")
        summary = make_summary(title, transcript, api_key)
        if summary:
            print("\n—— SUMMARY ——\n")
            print(summary)
            print("\n——————\n")
        else:
            sys.exit(1)
    else:  # Detailed description + chat
        print("\nGenerating detailed description …")
        desc = make_description(title, transcript, api_key)
        if desc:
            print("\n—— DETAILED DESCRIPTION ——\n")
            print(desc)
            print("\n——————\n")
        else:
            sys.exit(1)

        # Start chat
        start_chat_loop(title, transcript, api_key)


if __name__ == "__main__":
    main() 