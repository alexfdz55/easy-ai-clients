"""Shared output normalization and alignment helpers for speech synthesis.

Last updated: 2026-04-23
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from typing import Any

from pydub import AudioSegment

from .._transcribe._apis import deepgram as deepgram_transcribe
from .pre_processing import (
    WORD_PATTERN,
    decode_base64_bytes,
    infer_audio_format_from_name,
    normalize_comparison_token,
    normalize_timestamp_value,
    normalize_word_timestamps,
    tokenize_words,
)

try:
    import imageio_ffmpeg
except Exception:  # pragma: no cover - optional runtime dependency
    imageio_ffmpeg = None


WORD_GROUP_MAX_WINDOW_SECONDS = 1.2
WORD_GROUP_MAX_WORDS = 4


def build_chunk_record(
    *,
    text: str,
    audio_bytes: bytes,
    audio_format: str,
    observed_words: list[Mapping[str, Any]] | None = None,
    char_alignment: Mapping[str, Any] | None = None,
    timing_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the standard internal chunk payload consumed by synthesis post-processing."""
    chunk_payload: dict[str, Any] = {
        "text": str(text),
        "audio_bytes": bytes(audio_bytes or b""),
        "audio_format": str(audio_format).lower().replace(".", ""),
    }
    if observed_words:
        chunk_payload["observed_words"] = [dict(item) for item in observed_words]
    if char_alignment:
        chunk_payload["char_alignment"] = dict(char_alignment)
    if timing_events:
        chunk_payload["timing_events"] = [dict(item) for item in timing_events]
    return chunk_payload


def align_synthesized_audio_with_deepgram(
    audio_bytes: bytes,
    *,
    original_text: str,
    language: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Recover per-word timings via the shared Deepgram transcription adapter."""
    alignment_bundle = deepgram_transcribe.transcribe(
        audio_bytes,
        model="nova-3",
        fallback_model="whisper-large",
        concurrency=1,
        language=language,
        paragraphs=False,
        filler_words=False,
        numerals=True,
        measurements=True,
        detect_entities=False,
        language_mkd=False,
    )
    observed_words = [
        {
            "word": str(item.get("word") or "").strip(),
            "start": float(item.get("start", 0)) / 1000.0,
            "end": float(item.get("end", 0)) / 1000.0,
        }
        for _, item in sorted((alignment_bundle.get("words") or {}).items(), key=lambda pair: int(pair[0]))
        if isinstance(item, Mapping) and str(item.get("word") or "").strip()
    ]
    if not observed_words and str(original_text or "").strip():
        raise ValueError("Deepgram aligner did not return any words for synthesized audio.")
    cost_usd = alignment_bundle.get("cost_usd", 0.0)
    return observed_words, _coerce_cost_usd(cost_usd)


def build_aligned_chunk_record(
    *,
    text: str,
    audio_bytes: bytes,
    audio_format: str,
    language: str | None = None,
) -> tuple[dict[str, Any], float]:
    """Build one chunk payload after recovering timings through Deepgram."""
    observed_words, alignment_cost_usd = align_synthesized_audio_with_deepgram(
        audio_bytes,
        original_text=text,
        language=language,
    )
    return (
        build_chunk_record(
            text=text,
            audio_bytes=audio_bytes,
            audio_format=audio_format,
            observed_words=observed_words,
        ),
        alignment_cost_usd,
    )


def _finalize_synthesis_output(
    chunks: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    cost_usd: Any,
) -> dict[str, Any]:
    """Decode chunks, concatenate audio, and return the public synthesis payload."""
    if not isinstance(chunks, list | tuple) or not chunks:
        raise ValueError("chunks must include at least one synthesis chunk.")

    final_audio = AudioSegment.empty()
    projected_words: list[dict[str, Any]] = []
    offset_seconds = 0.0

    for chunk in chunks:
        if not isinstance(chunk, Mapping):
            raise TypeError("Each entry in 'chunks' must be a mapping.")

        chunk_audio = _decode_chunk_audio(chunk)
        chunk_duration_seconds = max(0.0, len(chunk_audio) / 1000.0)
        observed_words = _extract_chunk_observed_words(chunk, audio_duration_seconds=chunk_duration_seconds)
        chunk_words = _project_words_to_original_text(
            str(chunk.get("text") or ""),
            observed_words,
            audio_duration_seconds=chunk_duration_seconds,
        )

        # A word cannot outlast the audio of its own chunk. Providers sometimes report the
        # last word ending a little after the audio really does (2 ms on Multilingual v2,
        # 80 ms on Eleven v4 Turbo). The next chunk starts exactly where this audio ends,
        # so that overrun made its first word start before the previous one had finished,
        # and callers that require non-overlapping words rejected the whole narration.
        for word in chunk_words:
            start = min(float(word["start"]), chunk_duration_seconds)
            end = min(max(float(word["end"]), start), chunk_duration_seconds)
            projected_words.append(
                {
                    "word": word["word"],
                    "start": start + offset_seconds,
                    "end": end + offset_seconds,
                }
            )
        final_audio += chunk_audio
        offset_seconds += chunk_duration_seconds

    return {
        "cost_usd": _coerce_cost_usd(cost_usd),
        "cost_currency": "USD",
        "cost_source": "official_pricing_table" if _coerce_cost_usd(cost_usd) else "unavailable",
        "cost_is_estimated": True,
        "cost_details": {},
        "audio": final_audio,
        "words": _format_public_word_timestamps(projected_words),
    }


def _coerce_cost_usd(value: Any) -> float:
    """Normalize the public cost field into a float."""
    try:
        return round(max(0.0, float(value)), 6)
    except (TypeError, ValueError) as error:
        raise ValueError("cost_usd must be numeric.") from error


def _decode_chunk_audio(chunk: Mapping[str, Any]) -> AudioSegment:
    """Decode one chunk audio payload into an AudioSegment."""
    audio_bytes = chunk.get("audio_bytes")
    if audio_bytes:
        return _decode_audio_bytes_to_segment(bytes(audio_bytes), chunk_audio_format=chunk.get("audio_format"))

    audio_base64 = chunk.get("audio_base64")
    if audio_base64:
        return _decode_audio_bytes_to_segment(
            decode_base64_bytes(audio_base64),
            chunk_audio_format=chunk.get("audio_format"),
        )

    raise ValueError("Chunk did not include audio_bytes or audio_base64.")


def _decode_audio_bytes_to_segment(audio_bytes: bytes, *, chunk_audio_format: Any = None) -> AudioSegment:
    """Decode raw audio bytes into one AudioSegment, auto-detecting the format."""
    payload = bytes(audio_bytes or b"")
    if not payload:
        raise ValueError("Chunk audio payload is empty.")

    _configure_audiosegment_backend()
    ffmpeg_executable = _get_ffmpeg_executable()
    hinted_formats = _normalize_audio_formats(chunk_audio_format)
    for audio_format in hinted_formats:
        if ffmpeg_executable and _prefer_ffmpeg_decode(audio_format):
            try:
                return _decode_audio_bytes_with_ffmpeg(
                    payload,
                    audio_format=audio_format,
                    ffmpeg_executable=ffmpeg_executable,
                )
            except Exception:
                pass
        try:
            return AudioSegment.from_file(BytesIO(payload), format=audio_format)
        except Exception:
            continue

    if ffmpeg_executable:
        for audio_format in hinted_formats:
            try:
                return _decode_audio_bytes_with_ffmpeg(
                    payload,
                    audio_format=audio_format,
                    ffmpeg_executable=ffmpeg_executable,
                )
            except Exception:
                continue
    raise ValueError("Could not decode chunk audio into an AudioSegment.")


def _extract_chunk_observed_words(
    chunk: Mapping[str, Any],
    *,
    audio_duration_seconds: float,
) -> list[dict[str, Any]]:
    """Extract observed per-word timings from the supported kept-provider formats."""
    if isinstance(chunk.get("observed_words"), list):
        return _coerce_direct_words(chunk["observed_words"])

    char_alignment = chunk.get("char_alignment")
    if isinstance(char_alignment, Mapping):
        return _words_from_char_alignment(char_alignment)

    timing_events = chunk.get("timing_events")
    if isinstance(timing_events, list | tuple):
        return _words_from_timing_events(timing_events)

    if str(chunk.get("text") or "").strip():
        return _fallback_even_word_distribution(str(chunk.get("text") or ""), audio_duration_seconds)

    return []


def _coerce_direct_words(words: list[Any]) -> list[dict[str, Any]]:
    """Normalize direct chunk-level word timings."""
    base_words: list[dict[str, Any]] = []
    for item in words:
        if not isinstance(item, Mapping):
            raise TypeError("Each direct word timing must be a mapping.")
        word = str(item.get("word") or item.get("text") or "").strip()
        if not word:
            continue
        base_words.append(
            {
                "word": word,
                "start": item.get("start", 0.0),
                "end": item.get("end", item.get("start", 0.0)),
            }
        )

    normalized_words = normalize_word_timestamps(base_words)
    for item in normalized_words:
        if item["end"] < item["start"]:
            item["end"] = item["start"]
    return _explode_observed_words(normalized_words)


def _words_from_char_alignment(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project character-level timings into word spans."""
    characters = list(payload.get("characters") or [])
    start_key = str(payload.get("start_key") or "character_start_times_seconds")
    end_key = str(payload.get("end_key") or "character_end_times_seconds")
    start_times = payload.get(start_key) or []
    end_times = payload.get(end_key) or []
    if not len(characters) == len(start_times) == len(end_times):
        raise ValueError("char_alignment fields must have the same length.")

    unit = str(payload.get("unit") or "seconds")
    text = str(payload.get("text") or "".join(str(char) for char in characters))
    character_timings: list[tuple[float, float] | None] = [None] * len(text)
    text_index = 0
    for index, character in enumerate(characters):
        while text_index < len(text) and text[text_index] != character:
            text_index += 1
        if text_index >= len(text):
            continue
        character_timings[text_index] = (
            normalize_timestamp_value(start_times[index], unit=unit),
            normalize_timestamp_value(end_times[index], unit=unit),
        )
        text_index += 1

    words: list[dict[str, Any]] = []
    for match in WORD_PATTERN.finditer(text):
        start_seconds = None
        end_seconds = None
        for position in range(*match.span()):
            timing = character_timings[position]
            if timing is None:
                continue
            if start_seconds is None:
                start_seconds = timing[0]
            end_seconds = timing[1]
        if start_seconds is None or end_seconds is None:
            continue
        words.append({"word": match.group(), "start": start_seconds, "end": end_seconds})
    return _explode_observed_words(words)


def _words_from_timing_events(events: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    """Build words from provider streaming/SSE timestamp events."""
    observed_words: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_type = str(event.get("type") or "").strip().lower()
        if event_type == "conversation.item.word_timestamps":
            payload = event.get("timestamps") if isinstance(event.get("timestamps"), Mapping) else event
            words = payload.get("words") or []
            starts = payload.get("start_seconds") or []
            ends = payload.get("end_seconds") or []
            if len(words) == len(starts) == len(ends):
                observed_words.extend(
                    normalize_word_timestamps(
                        [
                            {
                                "word": words[index],
                                "start": starts[index],
                                "end": ends[index],
                            }
                            for index in range(len(words))
                            if str(words[index]).strip()
                        ]
                    )
                )
            continue

        if event_type == "timestamps":
            payload = event.get("word_timestamps") if isinstance(event.get("word_timestamps"), Mapping) else {}
            words = payload.get("words") or []
            starts = payload.get("start") or payload.get("start_seconds") or []
            ends = payload.get("end") or payload.get("end_seconds") or []
            if len(words) == len(starts) == len(ends):
                observed_words.extend(
                    normalize_word_timestamps(
                        [
                            {
                                "word": words[index],
                                "start": starts[index],
                                "end": ends[index],
                            }
                            for index in range(len(words))
                            if str(words[index]).strip()
                        ]
                    )
                )
            continue

        if event_type == "timestamp":
            timestamp = event.get("timestamp") or {}
            if str(timestamp.get("type") or "").strip().lower() != "word":
                continue
            time_payload = timestamp.get("time") or {}
            observed_words.extend(
                normalize_word_timestamps(
                    [
                        {
                            "word": str(timestamp.get("text") or "").strip(),
                            "start": time_payload.get("begin", 0),
                            "end": time_payload.get("end", 0),
                        }
                    ],
                    unit="milliseconds",
                )
            )

    return _explode_observed_words(observed_words)


def _explode_observed_words(words: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Split provider/STT words into word-like tokens while preserving timings."""
    exploded: list[dict[str, Any]] = []
    for item in words or []:
        word_text = str(item.get("word") or "").strip()
        if not word_text:
            continue

        start_seconds = float(item.get("start", 0.0))
        end_seconds = float(item.get("end", start_seconds))
        if end_seconds < start_seconds:
            end_seconds = start_seconds

        token_items = tokenize_words(word_text)
        if not token_items:
            exploded.append({"word": word_text, "start": start_seconds, "end": end_seconds})
            continue
        if len(token_items) == 1 and token_items[0]["word"] == word_text:
            exploded.append({"word": word_text, "start": start_seconds, "end": end_seconds})
            continue

        weights = [max(1, len(token["normalized"]) or len(token["word"])) for token in token_items]
        total_weight = float(sum(weights))
        cursor = start_seconds
        duration = end_seconds - start_seconds
        for index, token in enumerate(token_items):
            token_end = end_seconds if index == len(token_items) - 1 else cursor + duration * (weights[index] / total_weight)
            exploded.append({"word": token["word"], "start": cursor, "end": token_end})
            cursor = token_end
    return exploded


def _project_words_to_original_text(
    original_text: str,
    observed_words: list[Mapping[str, Any]],
    *,
    audio_duration_seconds: float,
) -> list[dict[str, Any]]:
    """Project provider/STT timings back onto the original text tokens."""
    original_tokens = tokenize_words(original_text)
    if not original_tokens:
        return []

    observed_tokens = _explode_observed_words(observed_words)
    if not observed_tokens:
        return _fallback_even_word_distribution(original_text, audio_duration_seconds)

    original_norms = [token["normalized"] for token in original_tokens]
    observed_norms = [normalize_comparison_token(word.get("word")) for word in observed_tokens]
    assignments: list[dict[str, Any] | None] = [None] * len(original_tokens)
    matcher = SequenceMatcher(a=original_norms, b=observed_norms, autojunk=False)

    for opcode, original_start, original_end, observed_start, observed_end in matcher.get_opcodes():
        if original_start == original_end:
            continue

        original_slice = original_tokens[original_start:original_end]
        observed_slice = observed_tokens[observed_start:observed_end]

        if opcode == "equal":
            for offset in range(min(len(original_slice), len(observed_slice))):
                observed_word = observed_slice[offset]
                assignments[original_start + offset] = {
                    "word": original_slice[offset]["word"],
                    "start": float(observed_word.get("start", 0.0)),
                    "end": float(observed_word.get("end", 0.0)),
                }
            continue

        if observed_slice:
            redistributed = _redistribute_times(
                [token["word"] for token in original_slice],
                observed_slice[0]["start"],
                observed_slice[-1]["end"],
            )
            for offset, item in enumerate(redistributed):
                assignments[original_start + offset] = item

    index = 0
    while index < len(assignments):
        if assignments[index] is not None:
            index += 1
            continue

        span_start = index
        while index < len(assignments) and assignments[index] is None:
            index += 1
        span_end = index

        previous_end = assignments[span_start - 1]["end"] if span_start > 0 and assignments[span_start - 1] else None
        next_start = assignments[span_end]["start"] if span_end < len(assignments) and assignments[span_end] else None
        redistributed = _redistribute_times(
            [token["word"] for token in original_tokens[span_start:span_end]],
            previous_end if previous_end is not None else 0.0,
            next_start if next_start is not None else audio_duration_seconds,
        )
        for offset, item in enumerate(redistributed):
            assignments[span_start + offset] = item

    projected_words: list[dict[str, Any]] = []
    cursor = 0.0
    for index, assignment in enumerate(assignments):
        item = assignment or {"word": original_tokens[index]["word"], "start": cursor, "end": cursor}
        start_seconds = max(0.0, float(item.get("start", cursor)))
        end_seconds = max(start_seconds, float(item.get("end", start_seconds)))
        if start_seconds < cursor:
            start_seconds = cursor
            end_seconds = max(end_seconds, start_seconds)
        projected_words.append(
            {
                "word": original_tokens[index]["word"],
                "start": start_seconds,
                "end": end_seconds,
            }
        )
        cursor = end_seconds

    return projected_words


def _redistribute_times(words: list[str], start_seconds: float, end_seconds: float) -> list[dict[str, Any]]:
    """Redistribute one time window across a list of target words."""
    clean_words = [str(word or "").strip() for word in words if str(word or "").strip()]
    if not clean_words:
        return []

    start_seconds = max(0.0, float(start_seconds))
    end_seconds = max(start_seconds, float(end_seconds))
    weights = [max(1, len(normalize_comparison_token(word)) or len(word)) for word in clean_words]
    total_weight = float(sum(weights))
    duration = end_seconds - start_seconds
    cursor = start_seconds
    redistributed: list[dict[str, Any]] = []
    for index, word in enumerate(clean_words):
        token_end = end_seconds if index == len(clean_words) - 1 else cursor + duration * (weights[index] / total_weight)
        redistributed.append({"word": word, "start": cursor, "end": token_end})
        cursor = token_end
    return redistributed


def _fallback_even_word_distribution(text: str, audio_duration_seconds: float) -> list[dict[str, Any]]:
    """Fallback timing distribution used only when no observed timings are available."""
    tokens = tokenize_words(text)
    if not tokens:
        return []
    return _redistribute_times(
        [token["word"] for token in tokens],
        0.0,
        max(0.0, float(audio_duration_seconds)),
    )


def _format_public_word_timestamps(words: list[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    """Format internal word timings as the public synthesis `words` mapping."""
    normalized_words: list[dict[str, Any]] = []
    for item in words or []:
        word = str(item.get("word", "")).strip()
        if not word:
            continue

        start_seconds = float(item.get("start", 0.0))
        end_seconds = float(item.get("end", start_seconds))
        if end_seconds < start_seconds:
            end_seconds = start_seconds

        normalized_words.append(
            {
                "word": word,
                "start": start_seconds,
                "end": end_seconds,
            }
        )

    result: dict[int, dict[str, Any]] = {}
    group_ids = _assign_group_ids(normalized_words)
    for index, item in enumerate(normalized_words):
        result[index] = {
            "word": item["word"],
            "start": _seconds_to_milliseconds(item["start"]),
            "end": _seconds_to_milliseconds(item["end"]),
            "group_id": int(group_ids.get(index, 0)),
        }
    return result


def _assign_group_ids(
    words: list[Mapping[str, Any]],
    *,
    max_window_seconds: float = WORD_GROUP_MAX_WINDOW_SECONDS,
    max_words: int = WORD_GROUP_MAX_WORDS,
) -> dict[int, int]:
    """Assign visual group ids using the same timing rules as transcription output."""
    if not words:
        return {}

    max_window_seconds = max(0.0, float(max_window_seconds))
    max_words = max(1, int(max_words))

    group_ids: dict[int, int] = {}
    group_index = 0
    group_start = float(words[0].get("start", 0.0))
    words_in_group = 0

    for word_index, word in enumerate(words):
        word_end = float(word.get("end", word.get("start", 0.0)))
        if word_index > 0 and (
            (word_end - group_start) > max_window_seconds
            or words_in_group >= max_words
        ):
            group_index += 1
            group_start = float(word.get("start", 0.0))
            words_in_group = 0

        group_ids[word_index] = group_index
        words_in_group += 1

    return group_ids


def _seconds_to_milliseconds(value: Any) -> int:
    """Convert seconds to rounded integer milliseconds."""
    return int(round(float(value) * 1000.0))


def _normalize_audio_formats(chunk_audio_format: Any) -> tuple[str, ...]:
    """Order likely audio formats with any explicit hint first."""
    hinted = infer_audio_format_from_name(str(chunk_audio_format or ""))
    ordered = [hinted] if hinted else []
    for audio_format in ("mp3", "wav", "ogg", "flac", "opus", "aac", "m4a", "pcm"):
        if audio_format not in ordered:
            ordered.append(audio_format)
    return tuple(ordered)


def _configure_audiosegment_backend() -> None:
    """Point pydub to an ffmpeg executable when one is available."""
    ffmpeg_executable = _get_ffmpeg_executable()
    if not ffmpeg_executable:
        return
    AudioSegment.converter = ffmpeg_executable
    AudioSegment.ffmpeg = ffmpeg_executable


def _get_ffmpeg_executable() -> str | None:
    """Return the preferred ffmpeg executable path for audio decoding."""
    if imageio_ffmpeg is not None:
        try:
            ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_executable = None
        if ffmpeg_executable:
            return ffmpeg_executable
    return shutil.which("ffmpeg")


def _prefer_ffmpeg_decode(audio_format: str) -> bool:
    """Return whether one format should skip direct pydub probing first."""
    return str(audio_format or "").strip().lower() not in {"wav", "wave"}


def _decode_audio_bytes_with_ffmpeg(
    audio_bytes: bytes,
    *,
    audio_format: str,
    ffmpeg_executable: str,
) -> AudioSegment:
    """Decode compressed audio bytes through ffmpeg when direct pydub decoding fails."""
    suffix = f".{audio_format}" if audio_format else ".bin"
    temp_path = Path("")
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_input:
            temp_input.write(audio_bytes)
            temp_input.flush()
            temp_path = Path(temp_input.name)
        completed = subprocess.run(
            [
                ffmpeg_executable,
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(temp_path),
                "-f",
                "wav",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        )
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
    wav_bytes = bytes(completed.stdout or b"")
    if not wav_bytes:
        raise ValueError("ffmpeg returned empty WAV bytes during decode.")
    return AudioSegment.from_file(BytesIO(wav_bytes), format="wav")


__all__ = [
    "WORD_GROUP_MAX_WINDOW_SECONDS",
    "WORD_GROUP_MAX_WORDS",
    "align_synthesized_audio_with_deepgram",
    "build_aligned_chunk_record",
    "build_chunk_record",
    "_finalize_synthesis_output",
]
