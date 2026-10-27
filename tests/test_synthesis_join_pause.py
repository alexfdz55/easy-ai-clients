"""The join between two chunks keeps the pause the same voice makes inside its chunks.

Providers return each chunk with very little silence around it. Glued together, the next
sentence started at a third of a normal pause: on Eleven v4 Turbo, 180 to 350 ms at the
join against 530 to 720 ms between sentences inside a chunk (measured on 2026-10-27).
Sending the provider the previous request and the next text did not change it.
"""

from __future__ import annotations

from io import BytesIO

from pydub import AudioSegment
from pydub.generators import Sine

from easy_ai_clients.audio._synthesize.post_processing import (
    DEFAULT_JOIN_PAUSE_MS,
    _finalize_synthesis_output,
    build_chunk_record,
)


def _chunk(text: str, layout: list[tuple[str, int]], words: list[tuple[str, int, int]]) -> dict:
    """A chunk built from spans of `voice` (a tone) and `silence`, in milliseconds, with its
    word timings in milliseconds."""
    audio = AudioSegment.silent(duration=0, frame_rate=44100)
    for kind, duration in layout:
        if kind == "voice":
            audio += Sine(220).to_audio_segment(duration=duration, volume=-20).set_frame_rate(44100)
        else:
            audio += AudioSegment.silent(duration=duration, frame_rate=44100)
    buffer = BytesIO()
    audio.export(buffer, format="wav")
    return build_chunk_record(
        text=text,
        audio_bytes=buffer.getvalue(),
        audio_format="wav",
        observed_words=[
            {"word": word, "start": start / 1000, "end": end / 1000} for word, start, end in words
        ],
    )


def _two_sentences(*, tail: int = 50, inner: int = 700, last: str = "cuatro.") -> dict:
    """«Uno dos. Tres cuatro.»: two sentences with `inner` ms between them."""
    return _chunk(
        f"Uno dos. Tres {last}",
        [("voice", 500), ("silence", inner), ("voice", 500), ("silence", tail)],
        [("Uno", 0, 250), ("dos.", 250, 500), ("Tres", 500 + inner, 750 + inner), (last, 750 + inner, 1000 + inner)],
    )


def _one_sentence(*, lead: int = 150) -> dict:
    return _chunk(
        "Cinco seis.",
        [("silence", lead), ("voice", 500)],
        [("Cinco", lead, lead + 250), ("seis.", lead + 250, lead + 500)],
    )


def _words(result: dict) -> list[dict]:
    return [result["words"][index] for index in sorted(result["words"])]


def test_the_join_gets_the_pause_the_voice_makes_between_sentences() -> None:
    # Inside the first chunk the voice pauses 700 ms between sentences; the join only has
    # 50 ms at the end of the first chunk and 150 ms at the start of the second.
    result = _finalize_synthesis_output([_two_sentences(), _one_sentence()], cost_usd=0.0)

    first_length = 500 + 700 + 500 + 50
    assert len(result["audio"]) == first_length + 500 + 150 + 500
    words = _words(result)
    assert [word["word"] for word in words] == ["Uno", "dos.", "Tres", "cuatro.", "Cinco", "seis."]
    # The words of the second chunk move with the silence that was added.
    assert words[4]["start"] == first_length + 500 + 150
    for previous, following in zip(words, words[1:]):
        assert previous["end"] <= following["start"]


def test_a_join_in_the_middle_of_a_sentence_gets_no_pause() -> None:
    result = _finalize_synthesis_output([_two_sentences(last="cuatro"), _one_sentence()], cost_usd=0.0)

    assert len(result["audio"]) == (500 + 700 + 500 + 50) + (150 + 500)


def test_a_join_with_enough_silence_is_left_as_it_came() -> None:
    result = _finalize_synthesis_output(
        [_two_sentences(tail=400), _one_sentence(lead=400)], cost_usd=0.0
    )

    assert len(result["audio"]) == (500 + 700 + 500 + 400) + (400 + 500)


def test_without_a_pause_to_measure_the_default_sentence_pause_is_used() -> None:
    first = _chunk(
        "Uno dos.",
        [("voice", 500), ("silence", 50)],
        [("Uno", 0, 250), ("dos.", 250, 500)],
    )

    result = _finalize_synthesis_output([first, _one_sentence()], cost_usd=0.0)

    added = DEFAULT_JOIN_PAUSE_MS["sentence"] - (50 + 150)
    assert len(result["audio"]) == 550 + added + 650


def test_a_join_after_a_comma_aims_for_the_pause_after_a_comma() -> None:
    # Inside the first chunk: 300 ms after a comma and 700 ms after a full stop.
    first = _chunk(
        "Uno, dos. Tres,",
        [("voice", 250), ("silence", 300), ("voice", 250), ("silence", 700), ("voice", 250), ("silence", 20)],
        [("Uno,", 0, 250), ("dos.", 550, 800), ("Tres,", 1500, 1750)],
    )

    result = _finalize_synthesis_output([first, _one_sentence(lead=30)], cost_usd=0.0)

    first_length = 250 + 300 + 250 + 700 + 250 + 20
    assert len(result["audio"]) == first_length + (300 - 20 - 30) + 30 + 500


def test_the_pause_is_measured_also_when_the_words_leave_no_gap() -> None:
    # Realigned timings (Deepgram) run each word up to the next one: «dos.» ends where «Tres»
    # starts, at the end of the 700 ms pause.
    first = _chunk(
        "Uno dos. Tres cuatro.",
        [("voice", 500), ("silence", 700), ("voice", 500), ("silence", 50)],
        [("Uno", 0, 250), ("dos.", 250, 1200), ("Tres", 1200, 1450), ("cuatro.", 1450, 1700)],
    )

    result = _finalize_synthesis_output([first, _one_sentence()], cost_usd=0.0)

    assert len(result["audio"]) == 1750 + (700 - 50 - 150) + 650


def test_a_single_chunk_is_left_as_it_came() -> None:
    result = _finalize_synthesis_output([_two_sentences()], cost_usd=0.0)

    assert len(result["audio"]) == 500 + 700 + 500 + 50


def test_chunks_without_provider_timings_still_get_the_default_pause() -> None:
    """With no timings there is nothing to measure inside the chunks, but the silence at the
    join can still be measured: it is filled up to the default."""
    voice = Sine(220).to_audio_segment(duration=500, volume=-20).set_frame_rate(44100)
    records = []
    for text, audio in (
        ("Uno dos.", voice + AudioSegment.silent(duration=50, frame_rate=44100)),
        ("Tres cuatro.", AudioSegment.silent(duration=150, frame_rate=44100) + voice),
    ):
        buffer = BytesIO()
        audio.export(buffer, format="wav")
        records.append(build_chunk_record(text=text, audio_bytes=buffer.getvalue(), audio_format="wav"))

    result = _finalize_synthesis_output(records, cost_usd=0.0)

    assert len(result["audio"]) == 550 + (DEFAULT_JOIN_PAUSE_MS["sentence"] - 200) + 650
