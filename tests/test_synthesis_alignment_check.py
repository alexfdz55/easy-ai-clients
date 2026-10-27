"""Provider word timings that miss the pauses of their own audio are realigned.

On 2026-10-27 an Eleven v4 Turbo request returned timings that put the word after each
pause about 0.9 s early, inside the silence: the subtitles and scene cuts of a 6-minute
video ran ahead of the voice from the second request on. Right timings have a word starting
where the voice comes back after every pause; those ones did at 23 of 43 pauses.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from easy_ai_clients.audio._synthesize import post_processing
from easy_ai_clients.audio._synthesize.post_processing import (
    _finalize_synthesis_output,
    build_chunk_record,
    realign_chunks_that_miss_pauses,
)

SENTENCE_MS = 600
PAUSE_MS = 500


def _audio(sentences: int) -> bytes:
    audio = AudioSegment.silent(duration=0, frame_rate=44100)
    for index in range(sentences):
        if index:
            audio += AudioSegment.silent(duration=PAUSE_MS, frame_rate=44100)
        audio += Sine(220).to_audio_segment(duration=SENTENCE_MS, volume=-20).set_frame_rate(44100)
    buffer = BytesIO()
    audio.export(buffer, format="wav")
    return buffer.getvalue()


def _right_words(sentences: int) -> list[dict]:
    """Two words per sentence, where the voice really is. In seconds."""
    words = []
    for index in range(sentences):
        start = index * (SENTENCE_MS + PAUSE_MS) / 1000
        words.append({"word": f"uno{index}", "start": start, "end": start + 0.3})
        words.append({"word": f"dos{index}.", "start": start + 0.3, "end": start + 0.6})
    return words


def _early_words(sentences: int) -> list[dict]:
    """The same words, but each sentence after a pause starts inside the silence, as on
    2026-10-27: the first word takes the pause and the second starts 0.3 s before the voice."""
    words = _right_words(sentences)
    for index in range(1, sentences):
        resume = index * (SENTENCE_MS + PAUSE_MS) / 1000
        words[2 * index].update(start=resume - 0.5, end=resume - 0.3)
        words[2 * index + 1].update(start=resume - 0.3, end=resume + 0.6)
    return words


def _text(sentences: int) -> str:
    return " ".join(f"uno{index} dos{index}." for index in range(sentences))


def _chunk(words: list[dict], sentences: int = 6) -> dict:
    return build_chunk_record(
        text=_text(sentences), audio_bytes=_audio(sentences), audio_format="wav", observed_words=words
    )


@pytest.fixture
def aligner(monkeypatch):
    calls = []

    def fake(audio_bytes, *, original_text, language=None):
        calls.append({"text": original_text, "language": language})
        return _right_words(6), 0.002

    monkeypatch.setattr(post_processing, "align_synthesized_audio_with_deepgram", fake)
    return calls


def test_right_timings_are_kept_without_realigning(aligner) -> None:
    chunks = [_chunk(_right_words(6))]

    cost, warnings = realign_chunks_that_miss_pauses(chunks, language="es")

    assert (cost, warnings, aligner) == (0.0, [], [])
    assert chunks[0]["observed_words"] == _right_words(6)


def test_timings_that_miss_the_pauses_are_replaced_by_the_realignment(aligner) -> None:
    chunks = [_chunk(_early_words(6))]

    cost, warnings = realign_chunks_that_miss_pauses(chunks, language="es")

    assert cost == 0.002 and warnings == []
    assert aligner == [{"text": _text(6), "language": "es"}]
    words = [
        post_processing._finalize_synthesis_output(chunks, cost_usd=0.0)["words"][index]
        for index in range(12)
    ]
    # The first word after the first pause starts where the voice comes back: 1.1 s.
    assert words[2]["start"] == 1100


def test_a_failed_realignment_keeps_the_provider_timings_and_says_so(monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("no key")

    monkeypatch.setattr(post_processing, "align_synthesized_audio_with_deepgram", broken)
    early = _early_words(6)
    chunks = [_chunk(early)]

    cost, warnings = realign_chunks_that_miss_pauses(chunks)

    assert cost == 0.0
    assert len(warnings) == 1 and "miss 5 of 5 pauses" in warnings[0] and "no key" in warnings[0]
    assert chunks[0]["observed_words"] == early


def test_too_few_pauses_are_not_judged(aligner) -> None:
    chunks = [_chunk(_early_words(3), sentences=3)]

    assert realign_chunks_that_miss_pauses(chunks) == (0.0, [])
    assert aligner == []


def test_elevenlabs_realigns_a_request_whose_timings_miss_the_pauses(monkeypatch, aligner) -> None:
    from easy_ai_clients.audio._synthesize._apis import elevenlabs

    def fake_chunk(*args, chunk_text, **kwargs):
        record = _chunk(_early_words(6))
        record.update(character_cost=0, request_id="tts-1")
        return [record]

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(elevenlabs, "_generate_chunk", fake_chunk)

    result = elevenlabs.generate(_text(6), model="eleven_v4_turbo", voice="v1", language_code="es")

    assert result["cost_details"]["alignment_usd"] == 0.002
    assert "warnings" not in result
    assert result["words"][2]["start"] == 1100
    assert aligner[0]["language"] == "es"
