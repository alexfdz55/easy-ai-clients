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


def _chunk_sizes(monkeypatch, model: str, characters: int) -> list[int]:
    """How many characters each ElevenLabs request would carry, without calling it."""
    from easy_ai_clients.audio._synthesize._apis import elevenlabs

    sizes: list[int] = []

    def fake_chunk(*args, chunk_text, **kwargs):
        sizes.append(len(chunk_text))
        return [{"character_cost": 0, "request_id": f"tts-{len(sizes)}"}]

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(elevenlabs, "_generate_chunk", fake_chunk)
    monkeypatch.setattr(
        elevenlabs,
        "_finalize_synthesis_output",
        lambda records, cost_usd: {"cost_usd": cost_usd, "cost_details": {}, "audio": object(), "words": {}},
    )
    sentence = "Una frase cualquiera de la narración. "
    text = (sentence * (characters // len(sentence) + 1))[:characters].rstrip()
    elevenlabs.generate(text, model=model, voice="v1")
    return sizes


def test_eleven_v4_and_v4_turbo_take_a_long_narration_in_one_request(monkeypatch) -> None:
    """The generic rule cut a 5,000-character model at 2,200: a narration of two and a half
    minutes was recorded in two requests, with a join in the middle. A whole request of
    4,178 characters on Eleven v4 Turbo took 55 s, well inside the 120 s timeout; the cut
    sits a little below that, at 4,000."""
    for model in ("eleven_v4", "eleven_v4_turbo"):
        assert len(_chunk_sizes(monkeypatch, model, 3732)) == 1
        assert len(_chunk_sizes(monkeypatch, model, 4000)) == 1
        beyond = _chunk_sizes(monkeypatch, model, 4400)
        assert len(beyond) == 2
        assert max(beyond) <= 4000


def test_the_other_elevenlabs_models_are_cut_where_they_were(monkeypatch) -> None:
    assert len(_chunk_sizes(monkeypatch, "eleven_v3", 2200)) == 1
    assert len(_chunk_sizes(monkeypatch, "eleven_v3", 2300)) == 2
    assert len(_chunk_sizes(monkeypatch, "eleven_multilingual_v2", 3200)) == 1
    assert len(_chunk_sizes(monkeypatch, "eleven_multilingual_v2", 3300)) == 2
