"""easy-ai-clients: a unified Python client for multimodal multi-provider AI.

Importing :mod:`easy_ai_clients` exposes ergonomic public submodules:

- :mod:`easy_ai_clients.text` - text-in / text-out generation.
- :mod:`easy_ai_clients.audio` - speech synthesis (`generate`) and speech
  recognition (`transcribe`).
- :mod:`easy_ai_clients.image` - image generation, editing, remixing, and
  vision/multimodal analysis.
- :mod:`easy_ai_clients.music` - lyric-based music generation with validated
  provider/model routing.
- :mod:`easy_ai_clients.video` - text-to-video, image-to-video, motion control,
  lip-sync, agent video, and translation generation.
- :mod:`easy_ai_clients.media` - provider asset upload and deletion helpers.
- :mod:`easy_ai_clients.webhooks` - provider webhook endpoint helpers.
- :mod:`easy_ai_clients.account` - account and billing lookup helpers.

Each operation accepts an ``api`` keyword argument identifying the provider to
use. The string must match the file name (without ``.py``) of the internal
provider module shipped with the library.

Example::

    from easy_ai_clients import text, audio, image, music, video, media, webhooks, account

    text.generate("hello", api="openai")
    audio.generate("hello world", api="openai")
    audio.transcribe("audio.mp3", api="deepgram")
    image.analyze("describe this", "photo.png", api="openai")
    image.edit("make it night", "photo.png", api="openai")
    image.generate("a corgi", api="openai")
    image.remix("studio ghibli", ["ref1.png", "ref2.png"], api="openai")
    music.generate("lyrics", api="runware", prompt="upbeat pop rock")
    video.generate("a corgi surfing", api="google")
"""

from __future__ import annotations

from . import account, audio, image, media, music, text, video, webhooks

__all__ = [
    "text",
    "audio",
    "image",
    "music",
    "video",
    "media",
    "webhooks",
    "account",
    "__version__",
]

__version__ = "0.16.0"
