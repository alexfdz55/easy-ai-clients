# HeyGen video.translate

Use HeyGen v3 video translation through `easy_ai_clients.video.translate(..., api="heygen")`.

Credential: `HEYGEN_KEY`.

```python
from easy_ai_clients import video

result = video.translate(
    video="source.mp4",
    output_languages=["Spanish"],
    api="heygen",
    sync=False,
)
```

This operation calls `POST /v3/video-translations`. Helper functions cover
translation list/get/update/delete, captions, language listing, and proofread
workflows.

## Async submit controls

- `webhook_url`: mapped to HeyGen `callback_url` on the translation request.
- `on_submitted(receipt)`: callback called right after a successful submit
  response.
- `submission`: previous submit receipt. When provided, the wrapper skips the
  submit call and resumes polling/result retrieval from that translation id.

