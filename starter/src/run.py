"""Index the corpus and evaluate retrieval on one benchmark split."""

import argparse
import json
import logging
import os
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus
from .store import PgVectorStore


def setup_logging(log_path: Path) -> None:
    """Log to console and to a file so page/extraction errors are kept."""
    log_path.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()

    starter = Path(__file__).resolve().parents[1]
    root = starter.parent
    results = starter / "results"
    setup_logging(results / f"run_log_{args.split}.txt")
    log = logging.getLogger("run")
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    load_dotenv(starter / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing from starter/.env")

    all_questions = json.loads(
        (root / "benchmark" / "questions.json").read_text(encoding="utf-8-sig")
    )
    questions = [q for q in all_questions if q["split"] == args.split]
    minimum = 15 if args.split == "dev" else 5
    if len(questions) < minimum:
        raise SystemExit(f"Expected at least {minimum} {args.split} questions")

    pages = load_corpus(root / "data" / "manifest.json")
    log.info("Loaded %d corpus pages", len(pages))

    # No silent fallback: MyEmbedder raises if Ollama is unreachable.
    embedder = MyEmbedder()
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()

    chunk_size = 500
    overlap = 50
    splitters = {
        "A": lambda page: fixed_size(page, size=chunk_size, overlap=overlap),
        "B": lambda page: by_paragraph(page, max_size=chunk_size),
    }

    removed = store.delete_strategies_except(set(splitters))
    if removed:
        log.info("Removed stale strategies from the table: %s", removed)

    ingest_stats = {}
    for strategy, split_page in splitters.items():
        started = perf_counter()
        chunks = [chunk for page in pages for chunk in split_page(page)]
        log.info("Embedding %s: %d chunks...", strategy, len(chunks))

        rows_before = store.count_rows(strategy)
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        store.upsert(strategy, chunks, vectors)
        rows_after = store.count_rows(strategy)
        if rows_after["rows"] != len(chunks) or (
            rows_after["distinct_chunk_ids"] != len(chunks)
        ):
            raise RuntimeError(f"{strategy}: reload produced duplicate rows")

        lengths = sorted(len(chunk.text) for chunk in chunks)
        ingest_stats[strategy] = {
            "chunk_count": len(chunks),
            "min_chunk_chars": lengths[0],
            "p25_chunk_chars": lengths[len(lengths) // 4],
            "median_chunk_chars": lengths[len(lengths) // 2],
            "mean_chunk_chars": round(sum(lengths) / len(lengths), 2),
            "p75_chunk_chars": lengths[3 * len(lengths) // 4],
            "max_chunk_chars": lengths[-1],
            "chunks_under_100_chars": sum(1 for n in lengths if n < 100),
            "total_chunk_chars": sum(lengths),
            "ingest_seconds": round(perf_counter() - started, 3),
            "reload_check": {"before": rows_before, "after": rows_after},
        }

    traces = []
    query_started = perf_counter()
    for question in questions:
        query_vector = embedder.embed_query(question["question"])
        for strategy, stored_strategy in (("A", "A"), ("B", "B"), ("C", "B")):
            # C applies the filter only when the question supplies one.
            applied_filter = question.get("filter") if strategy == "C" else None
            hits = store.search(
                stored_strategy, query_vector, top_k=3, filters=applied_filter
            )
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            trace["applied_filter"] = applied_filter
            traces.append(trace)
    query_seconds = round(perf_counter() - query_started, 3)

    metrics = summarize(traces)
    results.mkdir(exist_ok=True)

    trace_path = results / f"traces_{args.split}.json"
    summary_path = results / f"summary_{args.split}.json"
    summary = {
        "split": args.split,
        "run_started_utc": started_at,
        "model": embedder.model_name,
        "dimensions": embedder.dimensions,
        "embedding": embedder.version_info(),
        "vector_store": store.server_versions(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pypdf": version("pypdf"),
        },
        "corpus_pages": len(pages),
        "cost_usd": 0,
        "strategies": {
            "A": {"chunker": "fixed_size", "chunk_size": chunk_size,
                  "overlap": overlap, "filter": None},
            "B": {"chunker": "by_paragraph", "max_chunk_size": chunk_size,
                  "filter": None},
            "C": {"reuses_chunks_and_vectors_from": "B",
                  "filter": "chapter (only when the question supplies one)"},
        },
        "ingest": ingest_stats,
        "query_seconds_all_strategies": query_seconds,
        "metrics": metrics,
    }

    for path, data in ((trace_path, traces), (summary_path, summary)):
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    for strategy in ("A", "B", "C"):
        counts = metrics[strategy][args.split]
        total = counts["questions"]
        log.info(
            "%s %s | Hit@1 %d/%d | Evidence Hit@3 %d/%d | Page Hit@3 %d/%d "
            "| Filter compliant %d/%d",
            strategy, args.split, counts["hit_at_1"], total,
            counts["evidence_hit_at_3"], total, counts["page_hit_at_3"], total,
            counts["filter_compliant_top3"], counts["filter_questions"],
        )

    log.info("Saved %d traces to %s", len(traces), trace_path)
    log.info("Saved summary to %s", summary_path)


if __name__ == "__main__":
    main()
