"""Verify benchmark gold before (and independently of) retrieval runs.

Checks that every evidence_quote occurs on its gold page after the same
normalization used by the pipeline, that filter values exist in the corpus
and agree with the gold page, and that split/filter counts meet the lab rules.

Run from starter/:  python -m scripts.verify_benchmark
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import _normalize  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402

REQUIRED = ("id", "split", "question", "expected_answer", "gold_source_id",
            "gold_page", "evidence_quote")


def main() -> None:
    starter = Path(__file__).resolve().parents[1]
    root = starter.parent
    questions = json.loads(
        (root / "benchmark" / "questions.json").read_text(encoding="utf-8-sig")
    )
    pages = {
        (p.document_id, p.page): p for p in load_corpus(root / "data" / "manifest.json")
    }
    chapters = {p.metadata["chapter"] for p in pages.values()}

    rows, problems = [], []
    for q in questions:
        missing = [key for key in REQUIRED if not q.get(key)]
        page = pages.get((q["gold_source_id"], q["gold_page"]))
        found = bool(page) and _normalize(q["evidence_quote"]) in _normalize(page.text)
        flt = q.get("filter") or {}
        filter_ok = None
        if flt:
            # Filter value must exist in the corpus and agree with the gold page.
            filter_ok = bool(page) and flt.get("chapter") in chapters and all(
                page.metadata.get(k) == v for k, v in flt.items()
            )
        row = {
            "id": q["id"], "split": q["split"], "gold_page": q["gold_page"],
            "gold_chapter": page.metadata["chapter"] if page else None,
            "evidence_on_gold_page": found, "filter": flt or None,
            "filter_matches_gold_page": filter_ok, "missing_fields": missing,
        }
        rows.append(row)
        if missing or not found or filter_ok is False:
            problems.append(row)

    split_counts = Counter(q["split"] for q in questions)
    filter_counts = Counter(q["split"] for q in questions if q.get("filter"))
    report = {
        "questions": len(questions),
        "split_counts": dict(split_counts),
        "filter_question_counts": dict(filter_counts),
        "gold_chapter_counts": dict(Counter(r["gold_chapter"] for r in rows)),
        "rules": {
            "at_least_20": len(questions) >= 20,
            "at_least_15_dev_5_test": split_counts["dev"] >= 15
            and split_counts["test"] >= 5,
            "at_least_3_filter_with_1_test": sum(filter_counts.values()) >= 3
            and filter_counts["test"] >= 1,
            "all_evidence_found": all(r["evidence_on_gold_page"] for r in rows),
        },
        "problems": problems,
        "per_question": rows,
    }
    out = starter / "results" / "benchmark_verification.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("questions", "split_counts", "filter_question_counts",
                       "gold_chapter_counts", "rules")}, indent=2))
    print(f"Problems: {len(problems)}  -> {out}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
