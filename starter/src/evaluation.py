"""Evaluate retrieval against source pages and verified evidence."""

import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def evaluate_query(
    question: dict[str, Any], hits: list[dict[str, Any]]
) -> dict[str, Any]:
    evidence = _normalize(question["evidence_quote"])
    if not evidence:
        raise ValueError(f"{question['id']}: evidence_quote is empty")

    ranked_hits = []
    for rank, hit in enumerate(hits[:3], start=1):
        matches_evidence = (
            hit["document_id"] == question["gold_source_id"]
            and hit["page"] == question["gold_page"]
            and evidence in _normalize(hit["text"])
        )
        ranked_hits.append({
            **hit,
            "rank": rank,
            "evidence_match": matches_evidence,
        })

    requested_filter = question.get("filter") or {}
    filter_compliant = None
    if requested_filter:
        filter_compliant = all(
            all(hit["metadata"].get(key) == value
                for key, value in requested_filter.items())
            for hit in ranked_hits
        )

    return {
        "id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "requested_filter": question.get("filter"),
        "hits": ranked_hits,
        "hit_at_1": bool(ranked_hits and ranked_hits[0]["evidence_match"]),
        "evidence_hit_at_3": any(hit["evidence_match"] for hit in ranked_hits),
        # Supplementary only: gold page reached even if evidence is split.
        "page_hit_at_3": any(
            hit["document_id"] == question["gold_source_id"]
            and hit["page"] == question["gold_page"]
            for hit in ranked_hits
        ),
        "filter_compliant_top3": filter_compliant,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}

    for trace in traces:
        by_split = summary.setdefault(trace["strategy"], {})
        counts = by_split.setdefault(trace["split"], {
            "questions": 0,
            "hit_at_1": 0,
            "evidence_hit_at_3": 0,
            "page_hit_at_3": 0,
            "filter_questions": 0,
            "filter_compliant_top3": 0,
        })

        counts["questions"] += 1
        counts["hit_at_1"] += int(trace["hit_at_1"])
        counts["evidence_hit_at_3"] += int(trace["evidence_hit_at_3"])
        counts["page_hit_at_3"] += int(trace["page_hit_at_3"])
        if trace["filter_compliant_top3"] is not None:
            counts["filter_questions"] += 1
            counts["filter_compliant_top3"] += int(trace["filter_compliant_top3"])

    return summary