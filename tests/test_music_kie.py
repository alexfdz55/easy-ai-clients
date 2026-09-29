"""Kie.ai Suno music adapter tests without live provider calls."""

from __future__ import annotations

import json

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


# ── V6 por la API de tareas (spec 041 de Jaymaker, tanda 1b) ────────────────────────────


def _jobs_record(state="success", credits=12, tracks=None):
    """GET /jobs/recordInfo como lo devolvió Kie el 2026-09-28: resultJson es texto."""
    tracks = tracks if tracks is not None else [
        {"id": "audio-a", "audio_url": "https://cdn.example/v6-a.mp3", "duration": 29.96},
        {"id": "audio-b", "audio_url": "https://cdn.example/v6-b.mp3", "duration": 30.0},
    ]
    result = {"code": 200, "msg": "success", "task_id": "task-v6", "data": tracks}
    return {
        "code": 200,
        "data": {
            "taskId": "task-v6",
            "state": state,
            "resultJson": json.dumps(result) if state == "success" else "",
            "failCode": "" if state != "fail" else "500",
            "failMsg": "" if state != "fail" else "Internal Error",
            "creditsConsumed": credits,
        },
    }


def _no_network(*args, **kwargs):
    raise AssertionError("network")


def test_v6_sends_the_jobs_payload_with_real_duration(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, params=None, timeout=None):
        captured.update(method=method, url=url, payload=json_payload)
        return {"code": 200, "data": {"taskId": "task-v6"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    generation = kie_module.generate(
        TEST_LYRICS,
        model="V6",
        prompt=STYLE_TAGS,
        duration=30,
        gender="female",
        title="Morning Light",
        negative_tags=["long intro"],
    )

    payload = captured["payload"]
    assert captured["url"] == kie_module.JOBS_CREATE_ENDPOINT
    assert payload["model"] == "ai-music-api/generate"
    assert "callBackUrl" not in payload
    task_input = payload["input"]
    assert task_input["model"] == "V6"
    assert task_input["lyrics"] == TEST_LYRICS
    assert "prompt" not in task_input
    assert task_input["style"] == STYLE_TAGS  # sin la pista de duración de V5_5
    assert task_input["duration"] == 30
    assert task_input["custom_mode"] is True and task_input["instrumental"] is False
    assert task_input["vocal_gender"] == "f"
    assert task_input["negative_tags"] == "long intro"
    assert "persona_id" not in task_input
    assert generation["model"] == "V6"
    assert generation["request_id"] == "task-v6"
    assert generation["cost_details"]["duration_seconds"] == 30


def test_v6_sends_the_persona(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, **kwargs):
        captured["payload"] = kwargs["json_payload"]
        return {"code": 200, "data": {"taskId": "task-v6"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    generation = kie_module.generate(
        TEST_LYRICS, model="V6", prompt=STYLE_TAGS, persona_id="p-123", persona_model="voice_persona"
    )
    assert captured["payload"]["input"]["persona_id"] == "p-123"
    assert captured["payload"]["input"]["persona_model"] == "voice_persona"
    assert generation["cost_details"]["persona_model"] == "voice_persona"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"persona_id": "p-1"}, "persona_model"),
        ({"persona_id": "p-1", "persona_model": "voice"}, "persona_model"),
        ({"persona_id": " ", "persona_model": "voice_persona"}, "persona_id"),
    ],
)
def test_v6_rejects_an_incomplete_persona(kie_module, monkeypatch, kwargs, match):
    monkeypatch.setattr(kie_module, "request_json", _no_network)
    with pytest.raises(ValueError, match=match):
        kie_module.generate(TEST_LYRICS, model="V6", prompt=STYLE_TAGS, **kwargs)


def test_v5_5_refuses_a_persona(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", _no_network)
    with pytest.raises(ValueError, match="V6"):
        kie_module.generate(TEST_LYRICS, prompt=STYLE_TAGS, persona_id="p-1", persona_model="voice_persona")


@pytest.mark.parametrize("state", ["waiting", "queuing", "generating"])
def test_v6_status_stays_running(kie_module, monkeypatch, state):
    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: _jobs_record(state=state))
    generation = standard_generation("kie", "V6", "task-v6")
    assert kie_module.get_status(generation)["status"] == "running"


def test_v6_status_success_reads_takes_and_real_cost(kie_module, monkeypatch):
    calls = []

    def fake_request_json(method, url, **kwargs):
        calls.append((method, url, kwargs.get("params")))
        return _jobs_record()

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    generation = standard_generation("kie", "V6", "task-v6")
    result = kie_module.get_status(generation)

    assert calls == [("GET", kie_module.JOBS_STATUS_ENDPOINT, {"taskId": "task-v6"})]
    assert result["status"] == "completed"
    assert result["metadata"]["take_count"] == 2
    assert result["metadata"]["alternate_audio_url"] == "https://cdn.example/v6-b.mp3"
    assert result["metadata"]["take_audio_ids"] == ["audio-a", "audio-b"]
    assert result["cost_usd"] == pytest.approx(0.06)
    assert result["cost_is_estimated"] is False
    assert result["cost_source"] == "kie_credits_consumed"


def test_v6_failure_leads_with_kie_reason_and_task_id(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: _jobs_record(state="fail"))
    for call in (kie_module.get_status, kie_module.download_result):
        generation = standard_generation("kie", "V6", "task-v6")
        with pytest.raises(RuntimeError, match=r"state fail \(code 500: Internal Error\)") as caught:
            call(generation)
        assert caught.value.request_id == "task-v6"
        assert generation["status"] == "failed"


def test_v6_download_uses_the_first_take(kie_module, monkeypatch):
    downloaded = []

    def fake_download(generation, provider, audio_url, extension="mp3"):
        downloaded.append(audio_url)
        generation["output_path"] = "outputs/music/temp/kie/v6.mp3"
        generation["status"] = "completed"
        return generation

    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: _jobs_record())
    monkeypatch.setattr(kie_module, "download_generation_audio", fake_download)
    result = kie_module.download_result(standard_generation("kie", "V6", "task-v6"))

    assert downloaded == ["https://cdn.example/v6-a.mp3"]
    assert result["metadata"]["alternate_audio_url"] == "https://cdn.example/v6-b.mp3"
    assert result["metadata"]["take_durations"] == [29.96, 30.0]


def test_v6_download_without_tracks_fails_loudly(kie_module, monkeypatch):
    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: _jobs_record(tracks=[]))
    generation = standard_generation("kie", "V6", "task-v6")
    with pytest.raises(RuntimeError, match="did not include audio URLs"):
        kie_module.download_result(generation)
    assert generation["status"] == "failed"


def test_public_router_keeps_the_v6_second_take(kie_module, monkeypatch):
    from easy_ai_clients import music

    def fake_download(generation, provider, audio_url, extension="mp3"):
        generation["output_path"] = "outputs/music/temp/kie/v6.mp3"
        generation["status"] = "completed"
        return generation

    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: _jobs_record())
    monkeypatch.setattr(kie_module, "download_generation_audio", fake_download)
    public = music.download_result(standard_generation("kie", "V6", "task-v6"), api="kie")
    assert public["metadata"]["alternate_audio_url"] == "https://cdn.example/v6-b.mp3"
    assert public["metadata"]["take_audio_ids"] == ["audio-a", "audio-b"]


def test_create_persona_returns_the_immediate_id(kie_module, monkeypatch):
    captured = {}

    def fake_request_json(method, url, **kwargs):
        captured.update(url=url, payload=kwargs["json_payload"])
        return {"code": 200, "data": {"persona_id": "p-9", "name": "Voz A", "description": "pop"}}

    monkeypatch.setattr(kie_module, "request_json", fake_request_json)
    result = kie_module.create_persona(
        task_id="task-v6", audio_id="audio-a", name="Voz A", description="pop", vocal_start=3, vocal_end=28
    )
    assert captured["url"] == kie_module.JOBS_CREATE_ENDPOINT
    assert captured["payload"]["model"] == "ai-music-api/generate-persona"
    assert captured["payload"]["input"] == {
        "task_id": "task-v6",
        "audio_id": "audio-a",
        "name": "Voz A",
        "description": "pop",
        "vocal_start": 3.0,
        "vocal_end": 28.0,
    }
    assert result["persona_id"] == "p-9"


def test_create_persona_waits_for_the_task(kie_module, monkeypatch):
    answers = iter(
        [
            {"code": 200, "data": {"taskId": "persona-task"}},
            {"code": 200, "data": {"taskId": "persona-task", "state": "generating"}},
            {
                "code": 200,
                "data": {
                    "taskId": "persona-task",
                    "state": "success",
                    "resultJson": json.dumps({"resultObject": {"persona_id": "p-10"}}),
                },
            },
        ]
    )
    monkeypatch.setattr(kie_module, "request_json", lambda *a, **k: next(answers))
    monkeypatch.setattr(kie_module.time, "sleep", lambda seconds: None)
    result = kie_module.create_persona(task_id="t", audio_id="a", name="Voz B", description="balada")
    assert result == {"persona_id": "p-10", "request_id": "persona-task", "name": "Voz B", "description": "balada"}


@pytest.mark.parametrize(("start", "end"), [(0, 9), (0, 31), (-1, 20)])
def test_create_persona_checks_the_window(kie_module, monkeypatch, start, end):
    monkeypatch.setattr(kie_module, "request_json", _no_network)
    with pytest.raises(ValueError, match="vocal window"):
        kie_module.create_persona(
            task_id="t", audio_id="a", name="n", description="d", vocal_start=start, vocal_end=end
        )


def test_music_create_persona_only_for_kie(kie_module, monkeypatch):
    from easy_ai_clients import music

    monkeypatch.setattr(
        kie_module, "request_json", lambda *a, **k: {"code": 200, "data": {"persona_id": "p-1"}}
    )
    result = music.create_persona(api="kie", task_id="t", audio_id="a", name="n", description="d")
    assert result["persona_id"] == "p-1"
    with pytest.raises(ValueError, match="does not support personas"):
        music.create_persona(api="elevenlabs", task_id="t", audio_id="a", name="n", description="d")
