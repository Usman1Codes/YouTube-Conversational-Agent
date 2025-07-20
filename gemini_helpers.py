#!/usr/bin/env python3
"""gemini_helpers.py
Utility helpers to interact with Google Gemini for summary, detailed description
and interactive Q&A.

The module hides all prompt-engineering and error handling so that higher-level
code can call simple functions:

    summary = make_summary(title, transcript, api_key)
    description = make_description(title, transcript, api_key)
    start_chat_loop(title, transcript, api_key)
"""

from __future__ import annotations

import os
import sys
import textwrap
from typing import Optional

import google.generativeai as genai

# Gemini 1.5 Flash context window is large (>1M tokens), but we still enforce a
# hard cap on transcript length to keep latency predictable and cut costs.
_MAX_TRANSCRIPT_CHARS = 60_000  # ~15-20k tokens depending on language


# ────────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────────


def _get_model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash-latest")


def _prepare_transcript(transcript: str) -> str:
    if len(transcript) > _MAX_TRANSCRIPT_CHARS:
        # Simple truncation; for production you might implement smart chunking.
        transcript = transcript[:_MAX_TRANSCRIPT_CHARS]
    return transcript


# ────────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────────


def make_summary(title: str, transcript: str, api_key: str) -> Optional[str]:
    """Return a concise, high-quality summary or None on failure."""

    model = _get_model(api_key)
    transcript = _prepare_transcript(transcript)

    prompt = textwrap.dedent(
        f"""
        You are a senior content analyst. Read the transcript of a YouTube video
        titled "{title}" and produce an executive summary that:
        • Uses crisp bullet points (≤ 12 bullets).
        • Employs clear, non-technical language understandable by a layperson.
        • Covers every major argument, example, or data point.
        • Begins with one sentence answering the core question implied by the title.
        • If the title over-promises (clickbait), mention that in one bullet.

        Transcript:
        {transcript}
        """
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        print(f"[ERROR] Gemini summary failed: {exc}", file=sys.stderr)
        return None


def make_description(title: str, transcript: str, api_key: str) -> Optional[str]:
    """Return an in-depth description covering all aspects of the video."""

    model = _get_model(api_key)
    transcript = _prepare_transcript(transcript)

    prompt = textwrap.dedent(
        f"""
        You are a professional educator creating an in-depth explanation of a
        YouTube video titled "{title}". Using only the information contained in
        the transcript below, plus any widely-accepted background knowledge,
        write a detailed description with these sections:

        1. Overview – short paragraph summarising the central topic.
        2. Detailed Walk-through – structured with clear headings/sub-headings
           mirroring the video's flow. Include important details, facts, and any
           numerical data.
        3. Analysis – comment on the strength of arguments, evidence, or demos.
        4. Key Takeaways – numbered list.

        Keep it concise but comprehensive, aiming for ≲ 800 words.

        Transcript:
        {transcript}
        """
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        print(f"[ERROR] Gemini description failed: {exc}", file=sys.stderr)
        return None


def start_chat_loop(title: str, transcript: str, api_key: str) -> None:
    """Interactive Q&A based primarily on transcript content."""

    model = _get_model(api_key)
    transcript = _prepare_transcript(transcript)

    system_prompt = textwrap.dedent(
        f"""
        You have full access to the following YouTube video transcript (truncated
        if needed) for a video titled "{title}".

        – Always ground your answers in the transcript; cite specific moments or
          phrases when helpful.
        – If the transcript lacks the answer, you may use general knowledge or
          reason from context, but clarify the source (e.g. "Based on my general
          knowledge …").
        – If you truly don't know, say so concisely.
        – Keep answers short, direct, and avoid fluff.

        Transcript:
        {transcript}
        """
    )

    # Gemini chat does not support a 'system' role or system_instruction parameter in this client version.
    # Instead, embed the context as an initial user message.
    chat = model.start_chat(history=[{"role": "user", "parts": [system_prompt]}])

    print("Enter your questions about the video (type 'exit' or 'quit' to end):")

    while True:
        try:
            user_q = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()  # newline for clean exit
            break

        if user_q.strip().lower() in {"exit", "quit"}:
            break
        if not user_q.strip():
            continue

        try:
            resp = chat.send_message(user_q)
            print("Gemini:", resp.text.strip())
        except Exception as exc:
            print(f"[ERROR] Gemini chat failed: {exc}")

    print("Chat session ended.") 