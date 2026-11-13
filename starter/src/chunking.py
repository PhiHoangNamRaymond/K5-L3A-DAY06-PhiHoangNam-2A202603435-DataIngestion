"""Split source pages into chunks while preserving provenance."""

import re
import textwrap

from .models import Chunk, DocumentPage


def _make_chunks(
    page: DocumentPage, strategy: str, texts: list[str]
) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{page.document_id}:{page.page}:{strategy}:{index}",
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=text,
            metadata=page.metadata.copy(),
        )
        for index, text in enumerate(texts, start=1)
    ]


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Expected size > 0 and 0 <= overlap < size")

    text = " ".join(page.text.split())
    texts = []
    step = size - overlap

    for start in range(0, len(text), step):
        end = min(start + size, len(text))
        texts.append(text[start:end])
        if end == len(text):
            break

    return _make_chunks(page, "A", texts)


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("Expected max_size > 0")

    texts = []
    for block in re.split(r"\n[ \t]*\n+", page.text.strip()):
        paragraph = " ".join(block.split())
        if not paragraph:
            continue

        if len(paragraph) <= max_size:
            texts.append(paragraph)
            continue

        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        current = ""

        for sentence in sentences:
            if len(sentence) > max_size:
                if current:
                    texts.append(current)
                    current = ""
                texts.extend(textwrap.wrap(sentence, width=max_size))
                continue

            combined = f"{current} {sentence}" if current else sentence
            if len(combined) <= max_size:
                current = combined
            else:
                texts.append(current)
                current = sentence

        if current:
            texts.append(current)

    return _make_chunks(page, "B", texts)