"""The `results` command: add rows to the append-only results store and query them by run card.

CAPABILITIES:
  CAP-RESULTS-006: `python -m aqis_lab results add (--run DIR | --scores DIR [--run-card FILE]) [--store DIR]` stores a finished run's rows or a score folder's rows and reports how many were stored and how many were already stored; `results query --run-card ID [--store DIR]` prints the run card's rows as canonical JSON lines; exit 0 done, 1 conflict, integrity problem or no rows, 2 usage or input error [tests: test_FR_0_6_02_results_listed_by_dispatcher, test_FR_0_6_02_query_returns_rows_for_run_card, test_FR_0_6_02_query_unknown_run_card_exit_1, test_FR_0_6_02_query_rejects_malformed_id, test_FR_0_6_02_query_missing_store_exit_2, test_FR_0_6_02_add_exit_codes, test_FR_0_6_02_concurrent_adds_are_serialised]
INPUTS AND OUTPUTS: command-line arguments in; a report or JSON lines on stdout, `ERROR: ...` on stderr, exit 0, 1
  or 2.
CONTRACTS: store layout and query output in docs/results/RESULTS_STORE.md.
INVARIANTS:
  - The default store is data/raw/aqis_lab/results (git-ignored), the same as oracle.yaml's paths.results_store.
NOT IN SCOPE:
  - The store itself (aqis_lab/results/).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-02 created.
"""
import argparse
import sys

from aqis_lab.results.store import DEFAULT_STORE, RUN_CARD_ID_RE


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab results",
                                     description="Add rows to the append-only results store, or query them "
                                                 "(docs/results/RESULTS_STORE.md).")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add", help="store the rows of a finished run folder or of a score folder")
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", help="a finished run folder (run_card.json, shard_plan.json, results.jsonl)")
    source.add_argument("--scores", help="a `score` output folder (scores.parquet, scores.csv, summary.json)")
    add.add_argument("--run-card", default=None,
                     help="with --scores: the hypothesis run's run_card.json, when it is not in the store yet")
    add.add_argument("--store", default=str(DEFAULT_STORE), help=f"results store folder (default {DEFAULT_STORE})")
    query = sub.add_parser("query", help="print a run card's rows as JSON lines")
    query.add_argument("--run-card", required=True, help="run_card_id: 64 lowercase hexadecimal characters")
    query.add_argument("--store", default=str(DEFAULT_STORE), help=f"results store folder (default {DEFAULT_STORE})")
    return parser


def _add(ns):
    from aqis_lab.results import ingest, store
    if ns.run is not None:
        batch = ingest.from_run_folder(ns.run)
    else:
        batch = ingest.from_score_folder(ns.scores, run_card=ns.run_card)
    result = store.add_batch(ns.store, batch)
    where = f" in {result.part}" if result.part is not None else ""
    tail = f"; {result.already} already stored" if result.already else ""
    if result.part is None:
        tail += " (nothing written)" if not result.card_written else " (run card written)"
    print(f"stored {result.stored} row(s) for run card {result.run_card_id}{where}{tail}")
    return 0


def _query(ns):
    from aqis_lab.results import store, views
    if not RUN_CARD_ID_RE.fullmatch(ns.run_card):
        raise store.StoreInputError(f"--run-card must be a run_card_id: 64 lowercase hexadecimal characters, got "
                                    f"{ns.run_card!r}")
    records = views.query_run_card(ns.store, ns.run_card)
    if not records:
        print(f"ERROR: no rows for run card {ns.run_card} in the results store {ns.store}", file=sys.stderr)
        return 1
    for line in store.json_lines(records):
        print(line)
    return 0


def main(argv):
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.action == "add" and ns.run_card is not None and ns.scores is None:
        parser.error("--run-card goes with --scores (a run folder holds its own run card)")
    from aqis_lab.results.store import StoreConflictError, StoreInputError, StoreIntegrityError
    try:
        return _add(ns) if ns.action == "add" else _query(ns)
    except StoreInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (StoreConflictError, StoreIntegrityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
