"""BytePlus ModelArk Seedance 2.x image-to-video wrapper."""

from ... import _byteplus_common as common
from ..pre_processing import prepare_image_to_video

DEFAULT_MODEL = common.DEFAULT_MODEL


def generate_image_to_video(
    prompt,
    image_path=None,
    image_url=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    model = kwargs.pop("model", DEFAULT_MODEL)
    prepared = prepare_image_to_video(prompt, image_path, image_url, output_path)
    payload = common.build_generation_payload(
        model=model,
        prompt=prepared["prompt"],
        mode="image_to_video",
        kwargs=kwargs,
        first_image=prepared["image"],
    )
    return common.finalize_or_submit(
        model=model,
        payload=payload,
        output_path=prepared["output_path"],
        sync=bool(sync),
        timeout_seconds=kwargs.get("timeout_seconds"),
        poll_interval_seconds=kwargs.get("poll_interval_seconds"),
    )


def get_generation_status(request_id, **kwargs):
    return common.get_generation_status(request_id, **kwargs)


def get_generation_result(request_id, output_path=None, **kwargs):
    return common.get_generation_result(request_id, output_path=output_path, **kwargs)


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    return common.download_generation(
        request_id_value=request_id,
        video_url=video_url,
        output_path=output_path,
        **kwargs,
    )


__all__ = [
    "DEFAULT_MODEL",
    "download_generation",
    "generate_image_to_video",
    "get_generation_result",
    "get_generation_status",
]
