"""Shared Hedra video helpers."""

from __future__ import annotations

from collections.abc import Mapping

from .._submission_hooks import run_on_submitted
from ._shared import (
    hedra_async_refs,
    hedra_extract_video_url,
    hedra_get_generation_status,
    hedra_json,
    hedra_upload_local_asset,
    hedra_wait_for_result,
    merge_async_refs,
    normalize_hedra_status,
    normalize_output_path,
    require_env,
)

PROVIDER = "hedra"
ENV_NAME = "HEDRA_API_KEY"
COST_SOURCE = "hedra_models_catalog_snapshot_2026-05-14"

MODEL_DATA = {
    "grok-video-t2v": {"id": "827122cd-5fdd-4412-86f2-554f7bb8eef9", "name": "Grok Video T2V", "operation": "text_to_video", "credits_per_second": 7, "durations_ms": [5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["480p", "720p"]},
    "sora-2-pro-t2v": {"id": "6473f885-5f89-40f6-a26f-f3ad209ec59e", "name": "Sora 2 Pro T2V", "operation": "text_to_video", "credits_per_second": 70, "durations_ms": [4000, 8000, 12000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "veo-3-fast-t2v": {"id": "3b22668c-8e7e-48fb-a3b7-a509df3ccd2b", "name": "Veo 3 Fast T2V", "operation": "text_to_video", "credits_per_second": 20, "durations_ms": [4000, 6000, 8000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "veo-3-t2v": {"id": "d5af0ed3-c505-4495-802b-efb3e8ea741c", "name": "Veo 3 T2V", "operation": "text_to_video", "credits_per_second": 55, "durations_ms": [4000, 6000, 8000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "veo-2-t2v": {"id": "39ffdf48-52b3-4381-958c-030d0c501d73", "name": "Veo 2 T2V", "operation": "text_to_video", "credits_per_second": 40, "durations_ms": [5000], "aspect_ratios": ["16:9"], "resolutions": ["720p"]},
    "kling-v3-standard-t2v": {"id": "931b4681-c91e-40d7-91a1-bf743ceaf851", "name": "Kling V3 Standard T2V", "operation": "text_to_video", "credits_per_second": 18, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-v3-pro-t2v": {"id": "fcd99493-8a27-4f58-b40c-e03453fc4c64", "name": "Kling V3 Pro T2V", "operation": "text_to_video", "credits_per_second": 35, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-o3-standard-t2v": {"id": "b0e156da-da25-40b2-8386-937da7f47cc3", "name": "Kling O3 Standard T2V", "operation": "text_to_video", "credits_per_second": 30, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-o3-pro-t2v": {"id": "462fc9f9-ffb2-42cc-b4bf-e21224f0c181", "name": "Kling O3 Pro T2V", "operation": "text_to_video", "credits_per_second": 35, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-1.6-t2v": {"id": "8a014f26-9147-43ae-ae34-cb9d57476d4c", "name": "Kling 1.6 T2V", "operation": "text_to_video", "credits_per_second": 11, "durations_ms": [5000], "aspect_ratios": ["16:9"], "resolutions": ["720p"]},
    "kling-2.1-pro-t2v": {"id": "a9c3c80e-2be4-4836-9ff7-b4d12197a5fb", "name": "Kling 2.1 Pro T2V", "operation": "text_to_video", "credits_per_second": 15, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-2.1-master-t2v": {"id": "e10a919e-0c42-4782-b6b8-aba73b8f4b45", "name": "Kling 2.1 Master T2V", "operation": "text_to_video", "credits_per_second": 35, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-2.5-turbo-t2v": {"id": "936003b7-9409-459f-b796-0086a43a4794", "name": "Kling 2.5 Turbo T2V", "operation": "text_to_video", "credits_per_second": 10, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-2.6-pro-t2v": {"id": "10f248c9-688e-4213-9fb0-421327cccbd0", "name": "Kling 2.6 Pro T2V", "operation": "text_to_video", "credits_per_second": 20, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "minimax-hailuo-2.3-standard-t2v": {"id": "703f522b-688b-4a1d-b52b-5d91ee297fcb", "name": "MiniMax Hailuo 2.3 Standard T2V", "operation": "text_to_video", "credits_per_second": 6, "durations_ms": [6000, 10000], "aspect_ratios": ["16:9"], "resolutions": ["768p"]},
    "minimax-hailuo-2.3-pro-t2v": {"id": "1639d495-b614-43f6-942c-59afb8740cca", "name": "MiniMax Hailuo 2.3 Pro T2V", "operation": "text_to_video", "credits_per_second": 10, "durations_ms": [6000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "minimax-hailuo-02-standard-t2v": {"id": "d3e5529a-ee3d-486d-a64d-5d170f56800c", "name": "MiniMax Hailuo-02 Standard T2V", "operation": "text_to_video", "credits_per_second": 8, "durations_ms": [6000, 10000], "aspect_ratios": ["16:9"], "resolutions": ["768p"]},
    "minimax-hailuo-02-pro-t2v": {"id": "d2816cd3-cd32-4de2-8d41-6a2cb90511a9", "name": "MiniMax Hailuo-02 Pro T2V", "operation": "text_to_video", "credits_per_second": 16, "durations_ms": [6000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "seedance-2.0-t2v": {"id": "d1f0e387-fd9c-4750-bb43-8f93e0ddbc0c", "name": "Seedance 2.0 T2V", "operation": "text_to_video", "credits_per_second": 60, "durations_ms": [4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"], "resolutions": ["480p", "720p"]},
    "grok-video-i2v": {"id": "0435547d-1b30-41ad-bf66-ca476ff0564e", "name": "Grok Video I2V", "operation": "image_to_video", "credits_per_second": 7, "durations_ms": [5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["480p", "720p"]},
    "kling-v3-standard-i2v": {"id": "2eb5fa4c-306e-45f8-99e4-2927ec0429a0", "name": "Kling V3 Standard I2V", "operation": "image_to_video", "credits_per_second": 18, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-v3-pro-i2v": {"id": "08bd9806-874a-4ed8-a6b1-b83a77df665b", "name": "Kling V3 Pro I2V", "operation": "image_to_video", "credits_per_second": 35, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-o3-standard-i2v": {"id": "f8aff3cf-f5ab-4ec2-ac54-97865537fac5", "name": "Kling O3 Standard I2V", "operation": "image_to_video", "credits_per_second": 30, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-o3-pro-i2v": {"id": "a1a7f3a5-a4d6-4f19-92bf-ca3db3c8ddc5", "name": "Kling O3 Pro I2V", "operation": "image_to_video", "credits_per_second": 35, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-o1-i2v": {"id": "dcd6d7f4-c793-4045-a22a-48035a8431b3", "name": "Kling O1 I2V", "operation": "image_to_video", "credits_per_second": 20, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000], "aspect_ratios": ["16:9", "1:1", "9:16"], "resolutions": ["720p"]},
    "kling-1.6-i2v": {"id": "b5f854ca-6879-4018-b040-76084ceab97d", "name": "Kling 1.6 I2V", "operation": "image_to_video", "credits_per_second": 11, "durations_ms": [5000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "kling-2.1-pro-i2v": {"id": "5a57114f-4d51-4d59-88cd-6bb64015ebd2", "name": "Kling 2.1 Pro I2V", "operation": "image_to_video", "credits_per_second": 15, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-2.1-master-i2v": {"id": "80e2f925-20d9-4208-8d58-5ea6405822d8", "name": "Kling 2.1 Master I2V", "operation": "image_to_video", "credits_per_second": 35, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-2.5-turbo-i2v": {"id": "0e451fde-9e6f-48e6-83a9-222f6cc05eba", "name": "Kling 2.5 Turbo I2V", "operation": "image_to_video", "credits_per_second": 10, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "kling-2.6-pro-i2v": {"id": "f00f87c8-ec48-4e9c-bbb6-1e496c929f89", "name": "Kling 2.6 Pro I2V", "operation": "image_to_video", "credits_per_second": 20, "durations_ms": [5000, 10000], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["1080p"]},
    "minimax-hailuo-2.3-fast-standard-i2v": {"id": "b917e7da-f0a4-42d1-b52f-67ee11569cc8", "name": "MiniMax Hailuo 2.3 Fast Standard I2V", "operation": "image_to_video", "credits_per_second": 4, "durations_ms": [6000, 10000], "aspect_ratios": ["16:9"], "resolutions": ["768p"]},
    "minimax-hailuo-2.3-standard-i2v": {"id": "e64f6371-78a4-4143-b535-b69a17475ad6", "name": "MiniMax Hailuo 2.3 Standard I2V", "operation": "image_to_video", "credits_per_second": 6, "durations_ms": [6000, 10000], "aspect_ratios": ["16:9"], "resolutions": ["768p"]},
    "minimax-hailuo-2.3-fast-pro-i2v": {"id": "83bc198b-88cf-43cc-8d71-28d1a7f885d1", "name": "MiniMax Hailuo 2.3 Fast Pro I2V", "operation": "image_to_video", "credits_per_second": 7, "durations_ms": [6000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "minimax-hailuo-2.3-pro-i2v": {"id": "f2918f0e-0a51-411c-89d6-3ae1f74b6c67", "name": "MiniMax Hailuo 2.3 Pro I2V", "operation": "image_to_video", "credits_per_second": 10, "durations_ms": [6000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "minimax-hailuo-02-standard-i2v": {"id": "d11481da-b973-4e72-ade0-7e8a86915bbf", "name": "MiniMax Hailuo-02 Standard I2V", "operation": "image_to_video", "credits_per_second": 8, "durations_ms": [6000, 10000], "aspect_ratios": ["16:9"], "resolutions": ["768p"]},
    "minimax-hailuo-02-pro-i2v": {"id": "14404737-a366-4c84-a00f-6b2581db1435", "name": "MiniMax Hailuo-02 Pro I2V", "operation": "image_to_video", "credits_per_second": 16, "durations_ms": [6000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"]},
    "sora-2-pro-i2v": {"id": "b1ee5a44-0f2a-4bba-93ce-ee7420bdb6c1", "name": "Sora 2 Pro I2V", "operation": "image_to_video", "credits_per_second": 70, "durations_ms": [4000, 8000, 12000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "seedance-2.0-i2v": {"id": "17db7620-39bf-40c6-99d9-a4bbb7f305cf", "name": "Seedance 2.0 I2V", "operation": "image_to_video", "credits_per_second": 60, "durations_ms": [4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"], "resolutions": ["480p", "720p"]},
    "veo-3-fast-i2v": {"id": "9963e814-d1ee-4518-a844-7ed380ddbb20", "name": "Veo 3 Fast I2V", "operation": "image_to_video", "credits_per_second": 20, "durations_ms": [4000, 6000, 8000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "veo-3-i2v": {"id": "fb657777-6b02-478d-87a9-e02e8c53748c", "name": "Veo 3 I2V", "operation": "image_to_video", "credits_per_second": 55, "durations_ms": [4000, 6000, 8000], "aspect_ratios": ["16:9", "9:16"], "resolutions": ["720p", "1080p"]},
    "kling-o3-pro-edit-v2v": {"id": "9cf38eaf-d663-499c-9684-f2ca0b2bdd8e", "name": "Kling O3 Pro Edit V2V", "operation": "video_to_video", "credits_per_second": 35, "durations_ms": [5000], "aspect_ratios": ["16:9"], "resolutions": ["1080p"], "requires_input_video": True, "requires_start_frame": False, "requires_character_orientation": False, "max_duration_ms": 10000},
    "kling-o3-standard-edit-v2v": {"id": "57b6c36c-ecd9-4927-84f2-9a0c5ca08bd3", "name": "Kling O3 Standard Edit V2V", "operation": "video_to_video", "credits_per_second": 30, "durations_ms": [5000], "aspect_ratios": ["16:9"], "resolutions": ["720p"], "requires_input_video": True, "requires_start_frame": False, "requires_character_orientation": False, "max_duration_ms": 10000},
    "kling-o3-pro-reference-v2v": {"id": "33b7aa18-8abf-4422-a931-0a62468b8d02", "name": "Kling O3 Pro Reference V2V", "operation": "video_to_video", "credits_per_second": 35, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["auto", "16:9", "9:16", "1:1"], "resolutions": ["1080p"], "requires_input_video": True, "requires_start_frame": False, "requires_character_orientation": False, "max_duration_ms": 15000},
    "kling-o3-standard-reference-v2v": {"id": "9659607a-799d-4349-90d7-c27fe856d4c8", "name": "Kling O3 Standard Reference V2V", "operation": "video_to_video", "credits_per_second": 30, "durations_ms": [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000], "aspect_ratios": ["auto", "16:9", "9:16", "1:1"], "resolutions": ["720p"], "requires_input_video": True, "requires_start_frame": False, "requires_character_orientation": False, "max_duration_ms": 15000},
    "kling-2.6-motion-control-standard-vi2v": {"id": "780d5b45-3b39-46a6-aa6e-30ffc2ac8723", "name": "Kling 2.6 Motion Control Standard VI2V", "operation": "motion_control", "credits_per_second": 8, "durations_ms": ["auto"], "aspect_ratios": ["1:1", "16:9", "9:16"], "resolutions": ["720p"], "requires_input_video": True, "requires_start_frame": True, "requires_character_orientation": True, "max_duration_ms": 30000},
    "kling-2.6-motion-control-pro-vi2v": {"id": "10a4d9fb-491a-4ced-ac00-e980bf18e53f", "name": "Kling 2.6 Motion Control Pro VI2V", "operation": "motion_control", "credits_per_second": 16, "durations_ms": ["auto"], "aspect_ratios": ["1:1", "16:9", "9:16"], "resolutions": ["720p"], "requires_input_video": True, "requires_start_frame": True, "requires_character_orientation": True, "max_duration_ms": 30000},
    "hedra-avatar": {"id": "26f0fc66-152b-40ab-abed-76c43df99bc8", "name": "Hedra Avatar", "operation": "avatar_video", "credits_per_second": 7, "durations_ms": ["auto"], "aspect_ratios": ["1:1", "16:9", "9:16"], "resolutions": ["540p", "720p", "1080p"]},
    "hedra-character-3": {"id": "d1dd37a3-e39a-4854-a298-6510289f9cf2", "name": "Hedra Character 3", "operation": "avatar_video", "credits_per_second": 8, "durations_ms": ["auto"], "aspect_ratios": ["1:1", "16:9", "9:16"], "resolutions": ["540p", "720p", "1080p"]},
    "hedra-omnia": {"id": "ab372b84-432f-44f5-bacc-c2542465f712", "name": "Hedra Omnia", "operation": "avatar_video", "credits_per_second": 15, "durations_ms": ["auto"], "aspect_ratios": ["1:1", "16:9", "9:16"], "resolutions": ["540p", "720p", "1080p"]},
    "kling-ai-avatar-v2-standard": {"id": "d7eb3b2e-c8f8-45f9-83db-34f18dd0ba85", "name": "Kling AI Avatar v2 Standard", "operation": "avatar_video", "credits_per_second": 8, "durations_ms": ["auto"], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "kling-ai-avatar-v2-pro": {"id": "0451ceea-a7b5-4275-a970-82bf4ef38055", "name": "Kling AI Avatar v2 Pro", "operation": "avatar_video", "credits_per_second": 24, "durations_ms": ["auto"], "aspect_ratios": ["16:9", "9:16", "1:1"], "resolutions": ["720p"]},
    "veed-fabric-1.0": {"id": "5d1adc6d-3f67-486b-957f-cf3a858b5dec", "name": "VEED Fabric 1.0", "operation": "avatar_video", "credits_per_second": 30, "durations_ms": ["auto"], "aspect_ratios": ["16:9", "1:1", "4:3", "3:4", "9:16"], "resolutions": ["480p", "720p"]},
}

MODEL_ALIASES = {}
for key, value in MODEL_DATA.items():
    MODEL_ALIASES[key] = key
    MODEL_ALIASES[value["id"]] = key
    MODEL_ALIASES[value["name"].lower()] = key
MODEL_ALIASES["hedra_avatar"] = "hedra-avatar"


def resolve_model(model, default_key, operation):
    selected = model or default_key
    key = MODEL_ALIASES.get(str(selected).strip().lower())
    if key:
        data = MODEL_DATA[key]
        if data["operation"] != operation:
            raise ValueError(f"Hedra model `{selected}` is mapped to {data['operation']}, not {operation}.")
        return key, data
    return str(selected), {"id": str(selected), "name": str(selected), "operation": operation}


def duration_ms(model_data, kwargs):
    if kwargs.get("duration_ms") is not None:
        return int(kwargs["duration_ms"])
    value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
    if value is not None:
        return int(float(value) * 1000)
    durations = model_data.get("durations_ms") or []
    if durations and durations[0] != "auto":
        return int(durations[0])
    return None


def generated_video_inputs(prompt, model_data, kwargs):
    inputs = {}
    if prompt:
        inputs["text_prompt"] = prompt
    aspect_ratio = kwargs.get("aspect_ratio")
    if aspect_ratio is None and model_data.get("aspect_ratios"):
        aspect_ratio = model_data["aspect_ratios"][0]
    resolution = kwargs.get("resolution")
    if resolution is None and model_data.get("resolutions"):
        resolution = model_data["resolutions"][0]
    generation_duration_ms = duration_ms(model_data, kwargs)
    if aspect_ratio is not None:
        inputs["aspect_ratio"] = aspect_ratio
    if resolution is not None:
        inputs["resolution"] = resolution
    if generation_duration_ms is not None:
        inputs["duration_ms"] = generation_duration_ms
    for name in ("bounding_box_target", "enhance_prompt", "character_orientation"):
        if kwargs.get(name) is not None:
            inputs[name] = kwargs[name]
    return inputs


def hedra_cost(model_data, kwargs):
    credits_per_second = model_data.get("credits_per_second")
    if credits_per_second is None:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": True,
            "cost_source": "unavailable",
            "cost_credits": 0.0,
            "credit_source": "unavailable",
            "cost_reason": f"No Hedra catalog pricing metadata is available for `{model_data['name']}`.",
        }
    generation_duration_ms = duration_ms(model_data, kwargs)
    if generation_duration_ms is None:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": True,
            "cost_source": "unavailable",
            "cost_credits": 0.0,
            "credit_source": "Hedra model catalog",
            "cost_reason": "Hedra catalog pricing needs duration_seconds or duration_ms for this auto-duration model.",
        }
    videos = int(kwargs.get("batch_size", kwargs.get("number_of_videos", 1)))
    seconds = generation_duration_ms / 1000
    credits = credits_per_second * seconds * videos
    return {
        "cost_usd": 0.0,
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_credits": credits,
        "credit_source": "Hedra model catalog credits_per_second",
        "cost_reason": "Hedra charges credits; wrapper reports estimated credits because no public USD conversion is documented.",
    }


def submit_generation(payload, sync, output_path, model_data, cost, kwargs):
    api_key = require_env(ENV_NAME, "Hedra")
    webhook = str(kwargs.get("webhook_url") or "").strip()
    if webhook:
        raise ValueError("Hedra API does not support webhook_url for this operation.")
    submission = kwargs.get("submission")
    if submission is not None:
        if not isinstance(submission, Mapping):
            raise TypeError("submission must be a dictionary when provided.")
        raw = dict(submission)
    else:
        raw = hedra_json(
            "POST",
            "/generations",
            api_key,
            payload=payload,
            timeout_seconds=kwargs.get("timeout_seconds"),
        )
        run_on_submitted(kwargs.get("on_submitted"), raw)
    generation_id = raw.get("id") or raw.get("generation_id") or raw.get("request_id")
    if not generation_id and isinstance(raw.get("data"), Mapping):
        nested = raw.get("data") or {}
        generation_id = nested.get("id") or nested.get("generation_id") or nested.get("request_id")
    if not generation_id:
        raise RuntimeError("Hedra generation response did not include an id.")
    refs = hedra_async_refs(raw, generation_id)
    if not sync:
        extra = {**refs, "cost_reason": cost["cost_reason"], "cost_credits": cost["cost_credits"], "credit_source": cost["credit_source"]}
        return model_data["name"], generation_id, "submitted", None, normalize_output_path(output_path), raw, extra
    status = hedra_wait_for_result(
        generation_id,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        poll_interval_seconds=kwargs.get("poll_interval_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        poll_url=refs.get("poll_url"),
    )
    video_url = hedra_extract_video_url(status)
    if not video_url:
        raise RuntimeError(f"Hedra generation {generation_id} did not include a downloadable video URL.")
    extra = {**refs, "cost_reason": cost["cost_reason"], "cost_credits": cost["cost_credits"], "credit_source": cost["credit_source"]}
    return model_data["name"], generation_id, "completed", video_url, normalize_output_path(output_path), {"submission": raw, "result": status}, extra


def fetch_generation_status(request_id, kwargs):
    api_key = require_env(ENV_NAME, "Hedra")
    refs = merge_async_refs(None, kwargs, **hedra_async_refs({}, request_id))
    raw = hedra_get_generation_status(
        request_id,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        poll_url=refs.get("poll_url"),
    )
    refs = merge_async_refs(refs, raw)
    return raw, refs


def hedra_status_result(request_id, model_data, kwargs):
    raw, refs = fetch_generation_status(request_id, kwargs)
    return {
        "provider": PROVIDER,
        "model": model_data["name"],
        "request_id": request_id,
        "status": normalize_hedra_status(raw.get("status")),
        "raw_response": raw,
        **refs,
    }


def media_payload_key(path, url, asset_type, api_key, timeout_seconds=None):
    if path and url:
        raise ValueError(f"Provide either {asset_type}_path or {asset_type}_url, not both.")
    if path:
        return "id", hedra_upload_local_asset(path, asset_type, api_key, timeout_seconds)
    if url:
        return "url", str(url).strip()
    return None, None
