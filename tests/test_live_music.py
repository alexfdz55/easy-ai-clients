"""Gated live music smoke test.

This module submits a real music generation only when both
`EASY_AI_CLIENTS_LIVE_MUSIC=1` and `EASY_AI_CLIENTS_LIVE_MUSIC_API` are set by
the caller. Normal local validation keeps this gate cleared.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_FILE = ROOT.parent / ".env-easy-ai-clients"
LIVE_ENV = "EASY_AI_CLIENTS_LIVE_MUSIC"
API_ENV = "EASY_AI_CLIENTS_LIVE_MUSIC_API"
MODEL_ENV = "EASY_AI_CLIENTS_LIVE_MUSIC_MODEL"
ENV_FILE_ENV = "EASY_AI_CLIENTS_ENV_FILE"

PROVIDER_ENV = {
    "deapi": "DEAPI_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "google": "GOOGLE_API_KEY",
    "kie": "KIE_API_KEY",
    "runware": "RUNWARE_API_KEY",
}

PROVIDER_DURATION = {
    "deapi": 10,
    "elevenlabs": 3,
    "google": 30,
    "kie": 15,
    "runware": 30,
}
MODEL_DURATION = {
    "ace_step_v1_5_turbo": 10,
    "AceStep_1_5_Turbo": 10,
    "ace_step_1_5_xl_turbo_int8": 10,
    "AceStep_1_5_XL_Turbo_INT8": 10,
    "eleven_music": 3,
    "eleven_music_v2": 3,
    "music_v2": 3,
    "lyria_3_clip_preview": 30,
    "lyria-3-clip-preview": 30,
    "lyria_3_pro_preview": 15,
    "lyria-3-pro-preview": 15,
    "suno_v5_5": 15,
    "V5_5": 15,
    "ace_step_v1_5_xl_base": 30,
    "runware:ace-step@v1.5-xl-base": 30,
    "ace_step_v1_5_xl_sft": 30,
    "runware:ace-step@v1.5-xl-sft": 30,
    "ace_step_v1_5_xl_turbo": 30,
    "runware:ace-step@v1.5-xl-turbo": 30,
    "runware:ace-step@v1.5-turbo": 30,
}
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 900

PUBLIC_GENERATION_KEYS = {
    "provider",
    "model",
    "model_key",
    "status",
    "request_id",
    "output_path",
    "cost_usd",
    "cost_currency",
    "cost_source",
    "cost_is_estimated",
    "cost_details",
    "metadata",
}


def _require_live_enabled():
    if os.getenv(LIVE_ENV) != "1":
        pytest.skip(f"Set {LIVE_ENV}=1 to run a live music smoke test.")


def _load_credentials():
    if os.getenv(ENV_FILE_ENV):
        env_path = Path(os.environ[ENV_FILE_ENV])
        if not env_path.is_absolute():
            env_path = ROOT / env_path
        load_dotenv(env_path, override=False)
    load_dotenv(LOCAL_ENV_FILE, override=False)


def _selected_api():
    from easy_ai_clients import music

    api = str(os.getenv(API_ENV) or "").strip()
    if not api:
        pytest.skip(f"Set {API_ENV} to one of: {', '.join(music.available_apis())}.")
    if api not in music.available_apis():
        pytest.skip(f"{API_ENV}={api!r} is not supported by easy_ai_clients.music.")
    return api


def _require_env(api):
    env_var = PROVIDER_ENV[api]
    if not os.getenv(env_var):
        pytest.skip(f"{env_var} is not configured for live music smoke tests.")


def test_live_music_generation_smoke():
    from easy_ai_clients import music

    _require_live_enabled()
    _load_credentials()
    api = _selected_api()
    _require_env(api)

    model = str(os.getenv(MODEL_ENV) or "").strip()
    kwargs = {
        "lyrics": "[Verse]\nThe morning opens wide\n[Chorus]\nWe keep the light alive",
        "api": api,
        "style": "pop",
        "gender": "female",
        "duration": MODEL_DURATION.get(model, PROVIDER_DURATION[api]),
    }
    if model:
        kwargs["model"] = model

    output_path = None
    try:
        generation = music.generate(**kwargs)
        _assert_public_generation(generation, api)

        generation = _wait_for_completed_generation(music, generation, api)
        output_path = generation.get("output_path")
        downloaded = music.download_result(generation)
        _assert_public_generation(downloaded, api)

        output_path = downloaded.get("output_path")
        assert output_path
        path = Path(output_path)
        assert path.exists()
        assert path.stat().st_size > 0
    finally:
        _cleanup_live_output(output_path)


def _wait_for_completed_generation(music, generation, api):
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        updated = music.get_status(generation)
        _assert_public_generation(updated, api)
        if updated["status"] == "completed":
            return updated
        if updated["status"] == "failed":
            pytest.fail(f"live music generation failed for provider {api}")
        time.sleep(POLL_INTERVAL_SECONDS)
    pytest.fail(f"live music generation timed out for provider {api}")


def _assert_public_generation(generation, api):
    assert set(generation) == PUBLIC_GENERATION_KEYS
    assert generation["provider"] == api
    assert generation["request_id"]
    assert generation["status"] in {"submitted", "running", "completed"}
    assert "raw_response" not in generation


def _cleanup_live_output(output_path):
    if not output_path:
        return
    path = Path(output_path)
    try:
        resolved = path.resolve()
        temp_root = (Path.cwd() / "outputs" / "music" / "temp").resolve()
        resolved.relative_to(temp_root)
    except (OSError, ValueError):
        return
    if resolved.is_file():
        resolved.unlink()
    _remove_empty_parents(resolved.parent, temp_root)


def _remove_empty_parents(path, stop):
    current = path
    while current != stop and current.is_relative_to(stop):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
