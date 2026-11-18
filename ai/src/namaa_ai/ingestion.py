"""Layout/OCR ingestion contract and explicitly simulated local parser.

Production PDF/OCR is injected by an authorized backend document service; this
module never opens files, performs OCR, or creates trusted clinical context.
"""
from typing import Literal, Protocol

from .contracts import LayoutBlock, ParsedDocument


class DocumentParser(Protocol):
    def parse(self, *, source: str, source_version: str, media_type: str,
              payload: bytes) -> ParsedDocument: ...


class FixtureDocumentParser:
    """Test adapter returning hand-authored layout blocks; never claims real OCR."""
    def __init__(self, fixtures: dict[tuple[str, str], tuple[LayoutBlock, ...]]):
        self.fixtures = fixtures

    def parse(self, *, source: str, source_version: str, media_type: str,
              payload: bytes) -> ParsedDocument:
        del payload  # Fixture matching is by immutable source reference/version only.
        key = (source, source_version)
        if key not in self.fixtures:
            raise ValueError("parser_fixture_not_found")
        if media_type not in {"text/plain", "application/pdf", "image/tiff", "image/png", "image/jpeg"}:
            raise ValueError("unsupported_media_type")
        blocks = self.fixtures[key]
        if not blocks:
            raise ValueError("parser_returned_no_blocks")
        return ParsedDocument(
            source=source,
            source_version=source_version,
            media_type=media_type,
            parser_id="namaa-fixture-layout-parser",
            parser_revision="fixture-v1",
            extraction_method="native_text" if media_type == "text/plain" else "ocr",
            simulated=True,
            blocks=blocks,
        )
