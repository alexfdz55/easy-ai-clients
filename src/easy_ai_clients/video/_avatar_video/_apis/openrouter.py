"""OpenRouter avatar-video wrapper: one photo lip-synced to a supplied audio track."""

from ... import _openrouter_video_common as common

DEFAULT_MODEL = common.MODEL_HEYGEN_AVATAR_IV


def _public_url(path, url, name):
    """The provider downloads the photo and the audio itself: only public URLs work."""

    if path:
        raise ValueError(
            f"OpenRouter avatar video needs {name}_url: the provider downloads the file, "
            f"so a local {name}_path cannot be sent."
        )
    value = str(url or "").strip()
    if not value:
        return None
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError(f"{name}_url must be a public http(s) URL for OpenRouter avatar video.")
    return value


def generate_avatar_video(
    image_path=None,
    image_url=None,
    audio_path=None,
    audio_url=None,
    text=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    model = kwargs.pop("model", DEFAULT_MODEL)
    payload = common.build_avatar_payload(
        model=model,
        image=_public_url(image_path, image_url, "image"),
        audio=_public_url(audio_path, audio_url, "audio"),
        text=text,
        kwargs=kwargs,
    )
    return common.finalize_or_submit(
        model=model,
        payload=payload,
        output_path=output_path,
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
    "generate_avatar_video",
    "get_generation_result",
    "get_generation_status",
]
