#!/usr/bin/env python3
"""video_extractor.py
Module 2: Retrieve textual content from a YouTube video.

Attempt transcript download first using *youtube-transcript-api*. If that fails
(e.g. no captions, disabled, or language mismatch) fall back to audio download
with *yt-dlp* and speech-to-text transcription via the open-source *whisper*
model.

All heavy dependencies are imported lazily so that users who only ever need
captions don't pay the import cost of *yt_dlp* or *whisper*.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Iterable, Any

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

logger = logging.getLogger(__name__)

# Default to INFO level; let caller raise to DEBUG if desired.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)

# External lightweight language-detection library. Import lazily where used
try:
    from langdetect import detect, DetectorFactory  # type: ignore

    # Make detection deterministic across runs.
    DetectorFactory.seed = 0
except Exception:
    # Keep import optional - we fall back to slower STT if not present.
    detect = None  # type: ignore

# ────────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────────


def extract_text_from_video(
    video_id: str,
    video_url: Optional[str] = None,
    languages: List[str] | None = None,
    whisper_model: str = "base",
    max_retries: int = 3,
) -> Optional[str]:
    """Return a plain-text transcript for *video_id* or *None* on failure.

    Parameters
    ----------
    video_id
        The canonical 11-character YouTube ID.
    video_url
        *Optional* full URL. Only required for the audio-download fallback.
    languages
        Preferred caption languages ordered by priority. Defaults to
        `["en"]`.
    whisper_model
        Name of the *openai-whisper* model to use for STT if captions are not
        available. Ignored if fallback is not triggered.
    max_retries
        How many times to retry fetching captions when transient errors occur.
    """

    if languages is None:
        languages = ["en"]

    transcript = _fetch_youtube_transcript(video_id, languages, max_retries)
    if transcript:
        return transcript

    logger.info("Captions unavailable - falling back to audio download + STT…")

    if not video_url:
        # Construct a canonical watch URL.
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Use a temporary directory that cleans itself up even if errors occur.
    with tempfile.TemporaryDirectory(prefix="yt_audio_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        try:
            audio_path = _download_audio(video_url, tmp_dir=tmp_dir)
        except Exception as exc:
            logger.error("Failed to download audio for STT fallback: %s", exc)
            return None

        try:
            return _transcribe_audio(audio_path, model_name=whisper_model)
        except Exception as exc:
            logger.error("Whisper transcription failed: %s", exc)
            return None


# ────────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────────


def _join_snippets(snippets: Iterable[Any]) -> str:
    """Join caption snippets into a single whitespace-normalised string."""

    joined = " ".join(s.text.strip() for s in snippets if getattr(s, "text", "").strip())
    return joined.strip()


def _fetch_youtube_transcript(
    video_id: str,
    languages: List[str],
    max_retries: int,
) -> Optional[str]:
    """Robustly attempt to retrieve a transcript via YouTube's caption API.

    Strategy (in order):
    1. Manually created transcript in one of *languages*.
    2. Auto-generated transcript in one of *languages*.
    3. Any transcript that can be *translated* server-side to one of *languages*.
    4. Any transcript that appears to *contain* the desired language even if
       YouTube labelled it incorrectly (language detection).

    Only if all fail will the caller fall back to Whisper.
    """

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Attempt %s/%s: listing transcripts…", attempt, max_retries)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # 1. Manually-created in desired language
            try:
                return _join_snippets(
                    transcript_list.find_manually_created_transcript(languages).fetch()
                )
            except NoTranscriptFound:
                pass

            # 2. Auto-generated in desired language
            try:
                return _join_snippets(
                    transcript_list.find_generated_transcript(languages).fetch()
                )
            except NoTranscriptFound:
                pass

            # Convert to list for reuse
            all_transcripts = list(transcript_list)

            # 3. Translatable to desired language
            for lang in languages:
                for t in all_transcripts:
                    if getattr(t, "is_translatable", False):
                        try:
                            translated = t.translate(lang)
                            text = _join_snippets(translated.fetch())
                            if text:
                                logger.debug("Using translated transcript (%s → %s).", t.language_code, lang)
                                return text
                        except Exception:  # pragma: no cover - best effort
                            continue

            # 4. Mis-labelled transcripts - detect actual language
            if detect is not None:
                desired_set = {l.split("-")[0].lower() for l in languages}

                for t in all_transcripts:
                    try:
                        snippets = t.fetch()[:20]  # small sample for detection
                        sample = _join_snippets(snippets)
                        if not sample:
                            continue
                        detected_lang = detect(sample)  # type: ignore[arg-type]
                        if detected_lang.lower() in desired_set:
                            logger.debug(
                                "Using mis-labelled transcript %s (detected %s).", t.language_code, detected_lang
                            )
                            # Fetch the full transcript now.
                            return _join_snippets(t.fetch())
                    except Exception:
                        # Any error - skip and try next transcript
                        continue

            # If we reach here we haven't found suitable transcript.
            logger.info("No suitable captions after extended search.")
            return None

        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info("Transcripts disabled or none found for video %s.", video_id)
            return None  # Definitive - don't retry
        except Exception as exc:
            logger.debug(
                "Transient error (%s) during transcript fetch: %s", type(exc).__name__, exc
            )
            if attempt == max_retries:
                logger.error("Exceeded max retries for transcript fetch.")
                return None
            time.sleep(2)

    return None  # Unreachable


def _download_audio(video_url: str, *, tmp_dir: Path) -> Path:
    """Download the audio track with *yt-dlp* into *tmp_dir* and return the file path.

    The function prefers reasonably sized, compressed audio to keep download and
    processing time low. Whisper supports many codecs, so we avoid converting
    to huge WAV files.
    """

    from yt_dlp import YoutubeDL  # lazy import (heavy)

    ydl_opts = {
        # Filename without extension - yt-dlp will append proper ext.
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        # Prefer smaller formats (<20 MiB) when possible.
        "format": "bestaudio[filesize<20M]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        # No post-processing - keep original container (m4a/opus) to save space.
        "postprocessors": [],
    }

    with YoutubeDL(ydl_opts) as ydl:
        logger.info("Downloading audio… this may take a while.")
        info = ydl.extract_info(video_url, download=True)
        downloaded_path = Path(ydl.prepare_filename(info))

    if not downloaded_path.exists():
        raise FileNotFoundError("yt-dlp reported success but output file is missing.")

    logger.debug("Audio downloaded to %s", downloaded_path)
    return downloaded_path


def _transcribe_audio(audio_path: Path, model_name: str) -> str:
    """Transcribe *audio_path* to text using the *openai-whisper* library."""

    logger.info("Transcribing audio with Whisper (%s)…", model_name)

    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "The 'whisper' package is required for STT fallback. Install it via `pip install openai-whisper`."
        ) from exc

    # GPU / CPU selection - keep import local to avoid heavy torch import in
    # the captions-only path.
    try:
        import torch  # type: ignore

        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"

    logger.debug("Running Whisper on %s", device.upper())

    model = whisper.load_model(model_name, device=device)

    # fp16 only makes sense on GPU-capable devices.
    result = model.transcribe(str(audio_path), fp16=(device == "cuda"))

    return result.get("text", "").strip() 