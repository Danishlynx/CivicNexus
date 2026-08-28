"""Unit tests: Vision OCR client response handling (no network)."""

from typing import Any

import pytest
from civicnexus.tools import ocr


def _fake_post(payload: dict[str, Any]) -> Any:
    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        return payload

    return post


class TestImageExtraction:
    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ocr,
            "_post",
            _fake_post({"responses": [{"fullTextAnnotation": {"text": "FLOOR PLAN"}}]}),
        )
        assert ocr.extract_image_text("aGVsbG8=") == "FLOOR PLAN"

    def test_no_text_found_is_empty_not_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ocr, "_post", _fake_post({"responses": [{}]}))
        assert ocr.extract_image_text("aGVsbG8=") == ""

    def test_api_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ocr, "_post", _fake_post({"responses": [{"error": {"code": 3, "message": "bad"}}]})
        )
        with pytest.raises(ocr.OcrError, match="error"):
            ocr.extract_image_text("aGVsbG8=")

    def test_empty_responses_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ocr, "_post", _fake_post({"responses": []}))
        with pytest.raises(ocr.OcrError, match="no responses"):
            ocr.extract_image_text("aGVsbG8=")


class TestPdfExtraction:
    def test_pages_joined(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ocr,
            "_post",
            _fake_post(
                {
                    "responses": [
                        {
                            "responses": [
                                {"fullTextAnnotation": {"text": "page one"}},
                                {"fullTextAnnotation": {"text": "page two"}},
                            ]
                        }
                    ]
                }
            ),
        )
        assert ocr.extract_pdf_text("aGVsbG8=") == "page one\npage two"

    def test_page_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ocr,
            "_post",
            _fake_post({"responses": [{"responses": [{"error": {"message": "boom"}}]}]}),
        )
        with pytest.raises(ocr.OcrError, match="page error"):
            ocr.extract_pdf_text("aGVsbG8=")
