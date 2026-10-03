"""The words of a chunked narration never overlap at the join between two chunks.

A long text is synthesized in several requests and the audio is concatenated. The words of
each chunk are shifted by the duration of the audio before them. ElevenLabs sometimes
reports the last character of a chunk ending slightly AFTER that chunk's audio really ends
(2 ms on Multilingual v2, 80 ms on Eleven v4 Turbo, both seen in production in October
2026): the first word of the next chunk then started before the previous word had finished,
and SceneForge rejected the whole narration, already recorded and paid for.
"""

from __future__ import annotations

from io import BytesIO

from pydub import AudioSegment

from easy_ai_clients.audio._synthesize.post_processing import (
    _finalize_synthesis_output,
    build_chunk_record,
)


def _chunk(text: str, *, audio_ms: int, last_char_end: float) -> dict:
    """A chunk whose alignment spreads the characters evenly up to `last_char_end`."""
    buffer = BytesIO()
    AudioSegment.silent(duration=audio_ms).export(buffer, format="wav")
    step = last_char_end / len(text)
    return build_chunk_record(
        text=text,
        audio_bytes=buffer.getvalue(),
        audio_format="wav",
        char_alignment={
            "characters": list(text),
            "character_start_times_seconds": [index * step for index in range(len(text))],
            "character_end_times_seconds": [(index + 1) * step for index in range(len(text))],
        },
    )


def _words(result: dict) -> list[dict]:
    """The public words, in order. Their times are milliseconds."""
    return [result["words"][index] for index in sorted(result["words"])]


def test_a_word_never_outlasts_the_audio_of_its_chunk() -> None:
    # The alignment of the first chunk runs 80 ms past its one second of audio.
    chunks = [
        _chunk("sobre todo qué?", audio_ms=1000, last_char_end=1.08),
        _chunk("EL TERCER AYUDANTE", audio_ms=1000, last_char_end=0.9),
    ]

    words = _words(_finalize_synthesis_output(chunks, cost_usd=0.0))

    assert [word["word"] for word in words] == ["sobre", "todo", "qué?", "EL", "TERCER", "AYUDANTE"]
    last_of_first, first_of_second = words[2], words[3]
    assert last_of_first["end"] == 1000
    assert first_of_second["start"] == 1000
    for previous, following in zip(words, words[1:]):
        assert previous["end"] <= following["start"]
        assert previous["start"] <= previous["end"]


def test_chunks_whose_alignment_fits_the_audio_are_left_as_they_came() -> None:
    chunks = [
        _chunk("uno dos", audio_ms=1000, last_char_end=0.7),
        _chunk("tres", audio_ms=1000, last_char_end=0.4),
    ]

    words = _words(_finalize_synthesis_output(chunks, cost_usd=0.0))

    assert words[1]["end"] == 700
    assert (words[2]["start"], words[2]["end"]) == (1000, 1400)
