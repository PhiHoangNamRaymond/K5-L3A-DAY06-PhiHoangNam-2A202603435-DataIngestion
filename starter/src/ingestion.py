"""Read PDF pages selected by the corpus manifest."""

import hashlib
import json
import logging
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    *,
    page_numbers: range | None = None,
) -> list[DocumentPage]:
    reader = PdfReader(path)
    if page_numbers is None:
        page_numbers = range(1, len(reader.pages) + 1)

    pages = []
    for number in page_numbers:
        if not 1 <= number <= len(reader.pages):
            raise ValueError(f"Invalid PDF page {number} in {path}")

        try:
            raw_text = reader.pages[number - 1].extract_text() or ""
        except Exception:
            logger.exception("Could not extract page %s from %s", number, path)
            continue

        text = normalize_text(raw_text)
        if not text:
            logger.warning("No text on page %s in %s", number, path)
            continue

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=number,
                text=text,
            )
        )
    return pages


def load_corpus(manifest_path: Path) -> list[DocumentPage]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    repo_root = manifest_path.resolve().parent.parent
    corpus = []

    for document in manifest["documents"]:
        pdf_path = repo_root / document["local_path"]
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"{pdf_path} is missing; download it from "
                f"{document['source_path_or_url']} (see data/manifest.json)"
            )
        expected_hash = document.get("sha256")
        if expected_hash:
            actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                # A different PDF edition would shift page numbers and gold.
                raise ValueError(
                    f"{pdf_path.name}: sha256 {actual_hash} != manifest {expected_hash}"
                )
        document_pages = []
        for section in document["sections"]:
            page_numbers = range(
                section["pdf_page_start"], section["pdf_page_end"] + 1
            )
            pages = load_pdf(
                pdf_path,
                document["source_id"],
                document["source_path_or_url"],
                page_numbers=page_numbers,
            )
            for page in pages:
                page.metadata["chapter"] = section["chapter"]
                page.metadata["language"] = document["language"]
            document_pages.extend(pages)

        expected = document["included_page_count"]
        if len(document_pages) != expected:
            raise ValueError(
                f"{pdf_path.name}: expected {expected} pages, "
                f"extracted {len(document_pages)}"
            )
        corpus.extend(document_pages)

    return corpus