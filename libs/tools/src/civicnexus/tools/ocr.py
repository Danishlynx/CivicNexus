"""Deterministic OCR for applicant attachments — Cloud Vision, raw REST.

The keystone of the attachment pipeline's security design (2026-08-28
ruling): extraction is done by a TRANSCRIPTION engine, never a chat model.
OCR is not instruction-following — text hidden in pixels cannot prompt it —
so extracted text can then be screened as PLAIN TEXT, the screen measured
MOST sensitive (B-014: 11/15 fixture instructions match as bare text vs 2/15
inside PDFs). Reading capability and screening coverage move together.

Raw REST on purpose (the repo's F14-immune pattern): the endpoint is pinned,
auth is an explicit ADC bearer, and every failure raises ``OcrError`` — an
attachment that cannot be transcribed is NEVER fed onward unscreened.

Live-verified surface (2026-08-28, docs.cloud.google.com/vision):
- images: POST /v1/images:annotate, inline base64 ``image.content``;
- PDFs: POST /v1/files:annotate (synchronous), inline base64
  ``inputConfig.content`` — this field works ONLY on files:annotate — with
  at most 5 pages extracted per file;
- both with feature DOCUMENT_TEXT_DETECTION; text at
  ``fullTextAnnotation.text``.
"""

import os
from typing import Any

from civicnexus.otel import get_logger

_log = get_logger("ocr")

VISION_ENDPOINT = "https://vision.googleapis.com/v1"
#: files:annotate extracts at most 5 pages synchronously; we pin exactly that.
PDF_PAGES = [1, 2, 3, 4, 5]
_TIMEOUT_S = 60.0

IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
PDF_MIME_TYPE = "application/pdf"


class OcrError(Exception):
    """Extraction failed — the attachment must not proceed unscreened."""


def _bearer() -> str:
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())  # type: ignore[no-untyped-call]
    return str(credentials.token)


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    import requests

    headers = {"Authorization": f"Bearer {_bearer()}"}
    project = os.environ.get("PROJECT_ID", "")
    if project:
        # User ADC carries no quota project, and Vision refuses without one
        # (measured 403, 2026-08-28). Harmless under a service account.
        headers["x-goog-user-project"] = project
    response = requests.post(
        f"{VISION_ENDPOINT}/{path}",
        headers=headers,
        json=body,
        timeout=_TIMEOUT_S,
    )
    if not response.ok:
        raise OcrError(f"vision {path} HTTP {response.status_code}: {response.text[:300]}")
    payload: dict[str, Any] = response.json()
    return payload


def extract_image_text(image_b64: str) -> str:
    """Transcribe one inline image (base64). Returns the full text ('' if none)."""
    body = {
        "requests": [
            {
                "image": {"content": image_b64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    payload = _post("images:annotate", body)
    responses = payload.get("responses", [])
    if not responses:
        raise OcrError("vision images:annotate returned no responses")
    first = responses[0]
    if "error" in first:
        raise OcrError(f"vision images:annotate error: {first['error']}")
    return str(first.get("fullTextAnnotation", {}).get("text", ""))


def extract_pdf_text(pdf_b64: str) -> str:
    """Transcribe one inline PDF (base64), first 5 pages, synchronously."""
    body = {
        "requests": [
            {
                "inputConfig": {"content": pdf_b64, "mimeType": PDF_MIME_TYPE},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "pages": PDF_PAGES,
            }
        ]
    }
    payload = _post("files:annotate", body)
    file_responses = payload.get("responses", [])
    if not file_responses:
        raise OcrError("vision files:annotate returned no responses")
    first = file_responses[0]
    if "error" in first:
        raise OcrError(f"vision files:annotate error: {first['error']}")
    pages = first.get("responses", [])
    texts = []
    for page in pages:
        if "error" in page:
            raise OcrError(f"vision files:annotate page error: {page['error']}")
        text = page.get("fullTextAnnotation", {}).get("text", "")
        if text:
            texts.append(str(text))
    return "\n".join(texts)
