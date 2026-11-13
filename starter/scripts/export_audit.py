"""Export the fixed audit samples used for manual labelling.

Sampling rules were fixed before reading any scores:
- Coherence: the 10 lowest page IDs in the corpus (PDF pages 51-60). The
  position on each page is the sentence that contains the page's character
  midpoint. For each chunking strategy we export the chunk covering the
  start of that sentence. C reuses B's chunks, so C inherits B's labels.
- Metadata and grounding: all 5 test questions x top-3 x strategies A/B/C,
  read from results/traces_test.json. Metadata is also cross-checked
  programmatically against the PDF text and the manifest chapter ranges.

Run from starter/ after `python -m src.run --split test`:
    python -m scripts.export_audit
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.evaluation import _normalize  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402


def midpoint_sentence(text: str) -> str:
    flat = " ".join(text.split())
    sentences = [m for m in re.finditer(r"[^.!?]+[.!?]?", flat)]
    middle = len(flat) // 2
    for match in sentences:
        if match.start() <= middle < match.end():
            return match.group().strip()
    return sentences[len(sentences) // 2].group().strip()


def covering_chunk(chunks, anchor: str):
    anchor = _normalize(anchor)[:60]
    for chunk in chunks:
        if anchor in _normalize(chunk.text):
            return chunk
    # Anchor itself is split: return the chunk holding its first 25 chars.
    for chunk in chunks:
        if anchor[:25] in _normalize(chunk.text):
            return chunk
    return None


def main() -> None:
    starter = Path(__file__).resolve().parents[1]
    root = starter.parent
    out_dir = starter / "results" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / "data" / "manifest.json").read_text("utf-8-sig"))
    pages = load_corpus(root / "data" / "manifest.json")
    by_page = {(p.document_id, p.page): p for p in pages}

    coherence = []
    for page in sorted(pages, key=lambda p: p.page)[:10]:
        sentence = midpoint_sentence(page.text)
        row = {"page": page.page, "position_sentence": sentence}
        for name, chunks in (
            ("A", fixed_size(page, size=500, overlap=50)),
            ("B", by_paragraph(page, max_size=500)),
        ):
            chunk = covering_chunk(chunks, sentence)
            row[name] = {"chunk_id": chunk.chunk_id, "text": chunk.text} if chunk else None
        coherence.append(row)

    chapter_of = {}
    for document in manifest["documents"]:
        for section in document["sections"]:
            for n in range(section["pdf_page_start"], section["pdf_page_end"] + 1):
                chapter_of[(document["source_id"], n)] = section["chapter"]
        source_url = document["source_path_or_url"]

    traces = json.loads((starter / "results" / "traces_test.json").read_text("utf-8"))
    test_audit = []
    for trace in traces:
        hits = []
        for hit in trace["hits"]:
            page = by_page.get((hit["document_id"], hit["page"]))
            hits.append({
                "rank": hit["rank"], "chunk_id": hit["chunk_id"],
                "page": hit["page"], "source": hit["source"],
                "metadata": hit["metadata"], "score": round(hit["score"], 4),
                "evidence_match": hit["evidence_match"],
                "auto_check": {
                    "text_on_stated_page": bool(page) and _normalize(hit["text"])[:80]
                    in _normalize(page.text),
                    "chapter_matches_manifest":
                        hit["metadata"].get("chapter")
                        == chapter_of.get((hit["document_id"], hit["page"])),
                    "source_matches_manifest": hit["source"] == source_url,
                    "page_id_matches_chunk_id":
                        hit["chunk_id"].split(":")[1] == str(hit["page"]),
                },
                "text": hit["text"],
            })
        test_audit.append({
            "id": trace["id"], "strategy": trace["strategy"],
            "question": trace["question"], "expected_answer": trace["expected_answer"],
            "gold_page": trace["gold_page"], "evidence_quote": trace["evidence_quote"],
            "requested_filter": trace["requested_filter"],
            "applied_filter": trace["applied_filter"], "hits": hits,
        })

    for name, data in (("coherence_samples.json", coherence),
                       ("test_top3_samples.json", test_audit)):
        (out_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checks = [h["auto_check"] for t in test_audit for h in t["hits"]]
    print(f"Coherence positions: {len(coherence)}; test records: {len(checks)}")
    print("All auto metadata checks pass:",
          sum(all(c.values()) for c in checks), "/", len(checks))


if __name__ == "__main__":
    main()
