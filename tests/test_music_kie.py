"""Kie.ai Suno music adapter tests without live provider calls."""

from __future__ import annotations

import pytest

from easy_ai_clients.music._common import standard_generation
from easy_ai_clients.music._errors import MusicInputLimitError

TEST_LYRICS = "[Verse]\nThe morning opens wide\n[Chorus]\nWe keep the light alive"
STYLE_TAGS = "pop, catchy, high energy, 112 BPM, English vocals"


def _success_record(audio_urls=("https://cdn.example/a.mp3", "https://cdn.example/b.mp3")):
    suno_data = [
        {"audioUrl": audio_urls[0], "duration": 14.3},
        {"audioUrl": audio_urls[1], "duration": 10.5},
    ]
    return {
        "code": 200,
        "data": {
            "taskId": "task-1",
            "status": "SUCCESS",
            "response": {"sunoData": suno_data},
        },
    }


@pytest.fixture
def kie_module(monkeypatch):
    from easy_ai_clients.music._apis import kie

    monkeypatch.setattr(kie, "_headers", lambda: {"Authorization": "Bearer fake"})
    return kie


def test_generate_sends_custom_mode_payload(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = json_payload
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)

    generation = kie_module.generate(
        lyrics=TEST_LYRICS,
        prompt=STYLE_TAGS,
        duration=45,
        gender="female",
        title="Morning Light",
    )

    payload = captured["payload"]
    assert captured["method"] == "POST"
    assert captured["url"] == kie_module.GENERATE_ENDPOINT
    assert payload["prompt"] == TEST_LYRICS
    # Suno no acepta `duration`: viaja como pista dentro del estilo.
    assert payload["style"].startswith(STYLE_TAGS)
    assert "about 45 seconds long" in payload["style"]
    assert "duration" not in payload
    assert payload["title"] == "Morning Light"
    assert payload["customMode"] is True
    assert payload["instrumental"] is False
    assert payload["model"] == "V5_5"
    assert payload["vocalGender"] == "f"
    assert payload["callBackUrl"] == kie_module.DEFAULT_CALLBACK_URL
    assert generation["provider"] == "kie"
    assert generation["request_id"] == "task-1"
    assert generation["status"] == "submitted"
    assert generation["cost_usd"] == 0.06
    assert generation["cost_is_estimated"] is True
    assert "automatic music generation" not in payload["style"]


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (None, 60),
        ("abc", 60),
        (True, 60),
        (999, 360),
        (1, 10),
        ("75.9", 75),
    ],
)
def test_duration_is_normalized_before_payload(kie_module, monkeypatch, duration, expected):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured["payload"] = json_payload
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)

    kwargs = {"lyrics": TEST_LYRICS, "prompt": STYLE_TAGS}
    if duration is not None:
        kwargs["duration"] = duration

    kie_module.generate(**kwargs)
    # Kie no tiene campo de duración: la pista normalizada va en el estilo.
    assert "duration" not in captured["payload"]
    assert f"about {expected} seconds long" in captured["payload"]["style"]


def test_title_falls_back_to_first_lyric_line(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured["payload"] = json_payload
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    kie_module.generate(lyrics=TEST_LYRICS, prompt=STYLE_TAGS)
    assert captured["payload"]["title"] == "The morning opens wide"


def test_both_gender_omits_vocal_gender(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured["payload"] = json_payload
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    kie_module.generate(lyrics=TEST_LYRICS, prompt=STYLE_TAGS, gender="both")
    assert "vocalGender" not in captured["payload"]


def test_male_gender_maps_to_vocal_gender_m(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured["payload"] = json_payload
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    kie_module.generate(lyrics=TEST_LYRICS, prompt=STYLE_TAGS, gender="male")
    assert captured["payload"]["vocalGender"] == "m"


@pytest.mark.parametrize("status", ["PENDING", "FIRST_SUCCESS", "TEXT_SUCCESS"])
def test_non_success_statuses_stay_running(kie_module, monkeypatch, status):
    monkeypatch.setattr(
        kie_module,
        "request_json",
        lambda *args, **kwargs: {"code": 200, "data": {"taskId": "task-1", "status": status}},
    )
    generation = standard_generation("kie", "V5_5", "task-1")
    assert kie_module.get_status(generation)["status"] == "running"


def test_success_status_maps_to_completed(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", lambda *args, **kwargs: _success_record())
    generation = standard_generation("kie", "V5_5", "task-1")
    updated = kie_module.get_status(generation)
    assert updated["status"] == "completed"
    assert updated["metadata"]["take_count"] == 2
    assert updated["metadata"]["selected_take"] == 1
    assert updated["metadata"]["alternate_audio_url"] == "https://cdn.example/b.mp3"


def test_failed_status_raises(kie_module, monkeypatch):
    monkeypatch.setattr(
        kie_module,
        "request_json",
        lambda *args, **kwargs: {
            "code": 200,
            "data": {"taskId": "task-1", "status": "GENERATE_AUDIO_FAILED"},
        },
    )
    generation = standard_generation("kie", "V5_5", "task-1")
    with pytest.raises(RuntimeError, match="generate_audio_failed"):
        kie_module.get_status(generation)
    assert generation["status"] == "failed"


def test_download_uses_first_take_and_keeps_second_in_metadata(kie_module, monkeypatch):
    downloaded = []

    def fake_download(generation, provider, audio_url, extension="mp3"):
        downloaded.append(audio_url)
        generation["output_path"] = "outputs/music/temp/kie/result.mp3"
        generation["status"] = "completed"
        return generation

    monkeypatch.setattr(kie_module, "request_json", lambda *args, **kwargs: _success_record())
    monkeypatch.setattr(kie_module, "download_generation_audio", fake_download)

    generation = standard_generation("kie", "V5_5", "task-1")
    result = kie_module.download_result(generation)

    assert downloaded == ["https://cdn.example/a.mp3"]
    assert result["output_path"] == "outputs/music/temp/kie/result.mp3"
    assert result["metadata"]["alternate_audio_url"] == "https://cdn.example/b.mp3"
    assert result["metadata"]["take_count"] == 2


def test_download_waits_while_running(kie_module, monkeypatch):
    monkeypatch.setattr(
        kie_module,
        "request_json",
        lambda *args, **kwargs: {"code": 200, "data": {"taskId": "task-1", "status": "PENDING"}},
    )
    generation = standard_generation("kie", "V5_5", "task-1")
    assert kie_module.download_result(generation)["status"] == "running"


def test_generate_rejects_missing_prompt():
    from easy_ai_clients.music._apis import kie

    with pytest.raises(ValueError, match="prompt is required"):
        kie.generate(lyrics=TEST_LYRICS)


def test_style_and_lyrics_limits_raise_public_exception(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))

    with pytest.raises(MusicInputLimitError) as exc_info:
        kie_module.generate(lyrics="y" * 5001, prompt="x" * 1001)

    data = exc_info.value.to_dict()
    assert data["provider"] == "kie"
    assert data["fields"]["style"]["maximum"] == 1000
    assert data["fields"]["prompt"]["maximum"] == 5000


def test_generate_rejects_missing_task_id(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", lambda *args, **kwargs: {"code": 200, "data": {}})
    with pytest.raises(RuntimeError, match="taskId"):
        kie_module.generate(lyrics=TEST_LYRICS, prompt=STYLE_TAGS)


def test_non_success_code_raises(kie_module, monkeypatch):
    monkeypatch.setattr(
        kie_module,
        "request_json",
        lambda *args, **kwargs: {"code": 500, "msg": "boom", "data": {"taskId": "x"}},
    )
    with pytest.raises(RuntimeError, match="code 500"):
        kie_module.generate(lyrics=TEST_LYRICS, prompt=STYLE_TAGS)


def test_public_router_keeps_the_second_take_url_verbatim(kie_module, monkeypatch):
    """`sanitize` redacta todas las claves `*_url`; la segunda toma tiene que sobrevivir
    al diccionario público, porque el caller la baja antes de que caduque."""
    from easy_ai_clients import music

    def fake_download(generation, provider, audio_url, extension="mp3"):
        generation["output_path"] = "outputs/music/temp/kie/result.mp3"
        generation["status"] = "completed"
        return generation

    monkeypatch.setattr(kie_module, "request_json", lambda *args, **kwargs: _success_record())
    monkeypatch.setattr(kie_module, "download_generation_audio", fake_download)

    generation = standard_generation("kie", "V5_5", "task-1")
    public = music.download_result(generation, api="kie")
    assert public["metadata"]["alternate_audio_url"] == "https://cdn.example/b.mp3"
    assert public["metadata"]["take_count"] == 2
    assert generation["metadata"]["alternate_audio_url"] == "https://cdn.example/b.mp3"


def test_failure_message_leads_with_the_provider_reason(kie_module):
    """El motivo real (código y mensaje de Kie) va antes del payload recortado."""
    message = kie_module._failure_message(
        "status",
        {"status": "GENERATE_AUDIO_FAILED", "errorCode": 400, "errorMessage": "Your tags contain artist name skank", "param": "x" * 2000},
    )
    assert message.startswith("kie generation failed during status with status generate_audio_failed (code 400: Your tags contain artist name skank)")


def test_reggae_preset_has_no_artist_flagged_tag():
    from easy_ai_clients.music.styles import reggae

    assert "skank" not in repr(reggae.STYLE_PRESET).lower()


def test_negative_tags_travel_as_negativeTags(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, **kwargs):
        captured["payload"] = kwargs["json_payload"]
        return {"code": 200, "data": {"taskId": "task-1", "status": "PENDING"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    kie_module.generate(TEST_LYRICS, prompt=STYLE_TAGS, negative_tags=["long intro", "guitar solo"])
    assert captured["payload"]["negativeTags"] == "long intro, guitar solo"
    assert "negative_tags" not in captured["payload"]

    kie_module.generate(TEST_LYRICS, prompt=STYLE_TAGS)
    assert "negativeTags" not in captured["payload"]



def test_failures_carry_the_kie_task_id(kie_module, monkeypatch):
    # The message stays the same; the exception also says which task failed.
    monkeypatch.setattr(
        kie_module,
        "request_json",
        lambda *args, **kwargs: {
            "code": 200,
            "data": {"taskId": "task-1", "status": "GENERATE_AUDIO_FAILED"},
        },
    )
    for call in (kie_module.get_status, kie_module.download_result):
        generation = standard_generation("kie", "V5_5", "task-1")
        with pytest.raises(RuntimeError, match="generate_audio_failed") as caught:
            call(generation)
        assert caught.value.request_id == "task-1"
