#!/usr/bin/env python3
import argparse, csv, json, sys, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import evaluate_doc as ED
except Exception as e:
    sys.exit(f"Failed to import evaluate_doc.py: {e}")

ALLOWED_EXTS = {".pdf", ".txt"}

# ---------- Robust canonicalization ----------
# Strip common "barrier-free" markers from the END of the stem.
ID_TAIL_PATTERNS = [
    re.compile(r"(?i)[\s\-_]*bf(?:_uncompressed)?$"),         # ... bf / _bf / -bf / bf_uncompressed
    re.compile(r"(?i)[\s\-_]*barrier[\s\-_]*free$"),          # ... barrier-free / barrier_free / barrier free
]
# Normalize weird Unicode spaces to ASCII
SPACE_FIX = {ord("\u00A0"): " ", ord("\u202F"): " ", ord("\u2009"): " "}

def canonical_id(stem: str) -> str:
    s = stem.translate(SPACE_FIX).strip()
    for pat in ID_TAIL_PATTERNS:
        s = pat.sub("", s)
    return s.strip()

# Hypothesis stems: "<base>.response" or "<base>.response-2"
HYP_RESP_RE = re.compile(r"(?i)^(?P<base>.+?)\.response(?:-(?P<idx>\d+))?$")

def ref_doc_id(p: Path) -> str:
    return canonical_id(p.stem)

def hyp_doc_id_and_idx(p: Path) -> Tuple[str, int]:
    m = HYP_RESP_RE.match(p.stem)
    if m:
        base = canonical_id(m.group("base"))
        idx = int(m.group("idx") or "1")
        return base, idx
    # Fallback: treat plain same-name hypothesis as response 1
    return canonical_id(p.stem), 1

# ---------- Discovery ----------
def collect_refs(ref_dir: Path) -> Dict[str, Path]:
    refs: Dict[str, Path] = {}
    for p in ref_dir.iterdir():
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            did = ref_doc_id(p)
            # Prefer PDF if both .pdf and .txt exist
            if did in refs:
                if p.suffix.lower() == ".pdf" and refs[did].suffix.lower() != ".pdf":
                    refs[did] = p
            else:
                refs[did] = p
    return refs

def find_hypotheses(model_dir: Path) -> Dict[str, List[Tuple[int, Path]]]:
    hyps: Dict[str, List[Tuple[int, Path]]] = {}
    for p in model_dir.iterdir():
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            base, idx = hyp_doc_id_and_idx(p)
            hyps.setdefault(base, []).append((idx, p))
    for base in hyps:
        hyps[base].sort(key=lambda t: t[0])
    return hyps

# ---------- Aggregation helpers ----------
NUM_FIELDS = [
    "bleu","rouge_l_f1","meteor","lr","ls","cer","wer",
    "edit_distance_chars","edit_distance_tokens",
    "ref_length_chars","hyp_length_chars","ref_length_tokens","hyp_length_tokens"
]

def safe_mean(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if isinstance(v, (int, float))]
    return (sum(vals)/len(vals)) if vals else None

def best_per_doc(rows: List[dict]) -> List[dict]:
    by_doc: Dict[str, List[dict]] = {}
    for r in rows:
        key = f"{r['model']}::{r['doc_id']}"
        by_doc.setdefault(key, []).append(r)

    def score(r: dict) -> float:
        up = (
            (r.get("bleu") or 0.0) * 2.0 +
            (r.get("rouge_l_f1") or 0.0) * 1.5 +
            (r.get("meteor") or 0.0) * 1.5 +
            (r.get("lr") or 0.0) * 1.0 +
            (r.get("ls") or 0.0) * 1.0
        )
        down = 0.0
        for k, w in [("cer", 1.5), ("wer", 1.5), ("edit_distance_chars", 1.0), ("edit_distance_tokens", 1.0)]:
            v = r.get(k)
            down += w * (v if isinstance(v, (int, float)) else 1e9)
        return up - 0.001 * down

    best_rows = []
    for _, cand_rows in by_doc.items():
        cand_rows = sorted(cand_rows, key=score, reverse=True)
        best_rows.append(cand_rows[0])
    return best_rows

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Batch evaluate models with multiple responses per document.")
    ap.add_argument("--refs", required=True, type=Path, help="Directory with reference files (.pdf/.txt)")
    ap.add_argument("--models-root", required=True, type=Path, help="Directory whose subfolders are model names")
    ap.add_argument("--outdir", required=True, type=Path, help="Where to write metrics.jsonl/.csv and summaries")
    ap.add_argument("--method", choices=["rendered","streams"], default="rendered",
                    help="PDF extraction (for both refs and hyps) if files are PDFs.")
    ap.add_argument("--filter-pdfops", action="store_true",
                    help="Ignore PDF graphics ops & numbers during tokenisation.")
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path  = args.outdir / "metrics.jsonl"
    csv_path    = args.outdir / "metrics.csv"
    summary_csv = args.outdir / "summary_by_model.csv"
    best_summary_csv = args.outdir / "summary_by_model_docbest.csv"

    refs = collect_refs(args.refs)
    if not refs:
        sys.exit(f"No reference files found in {args.refs}")

    model_dirs = [d for d in args.models_root.iterdir() if d.is_dir()]
    if not model_dirs:
        sys.exit(f"No model folders found in {args.models_root}")

    jsonl_f = jsonl_path.open("a", encoding="utf-8")
    csv_f = csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_f, fieldnames=[
        "model","doc_id","response_index",
        "file_reference","file_candidate","extraction_method","filter_pdfops", *NUM_FIELDS
    ])
    writer.writeheader()

    all_rows: List[dict] = []

    for mdir in model_dirs:
        model_name = mdir.name
        hyps = find_hypotheses(mdir)

        for doc_id, ref_path in refs.items():
            cand_list = hyps.get(doc_id)
            if not cand_list:
                # Show a few available IDs to help debugging mismatches
                sample_ids = ", ".join(list(hyps.keys())[:5])
                print(f"[WARN] Missing hypothesis for {doc_id} in {model_name} "
                      f"(have: {sample_ids}{'...' if len(hyps)>5 else ''})", file=sys.stderr)
                continue

            ref_text = ED._extract_text(ref_path, args.method)
            if not ref_text.strip():
                print(f"[WARN] Empty reference extract for {doc_id}", file=sys.stderr)
                continue

            for resp_idx, hyp_path in cand_list:
                hyp_text = ED._extract_text(hyp_path, args.method)
                if not hyp_text.strip():
                    print(f"[WARN] Empty hypothesis extract for {doc_id} "
                          f"(model {model_name}, response {resp_idx})", file=sys.stderr)
                    continue

                metrics = ED._compute_metrics(ref_text, hyp_text, filtered=args.filter_pdfops)
                row = {
                    "model": model_name,
                    "doc_id": doc_id,
                    "response_index": resp_idx,
                    "file_reference": str(ref_path),
                    "file_candidate": str(hyp_path),
                    "extraction_method": args.method,
                    "filter_pdfops": args.filter_pdfops,
                    **{k: metrics.get(k) for k in NUM_FIELDS},
                }
                writer.writerow(row)
                all_rows.append(row)

                record = {
                    "model": model_name,
                    "doc_id": doc_id,
                    "response_index": resp_idx,
                    "file_reference": str(ref_path),
                    "file_candidate": str(hyp_path),
                    "extraction_method": args.method,
                    "filter_pdfops": args.filter_pdfops,
                    **metrics
                }
                jsonl_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    jsonl_f.close()
    csv_f.close()

    # Summaries
    by_model: Dict[str, List[dict]] = {}
    for r in all_rows:
        by_model.setdefault(r["model"], []).append(r)
    with summary_csv.open("w", newline="", encoding="utf-8") as sf:
        sw = csv.DictWriter(sf, fieldnames=["model", *NUM_FIELDS])
        sw.writeheader()
        for model_name, rows in by_model.items():
            agg = {"model": model_name}
            for k in NUM_FIELDS:
                agg[k] = safe_mean([r.get(k) for r in rows])
            sw.writerow(agg)

    best_rows = best_per_doc(all_rows)
    by_model_best: Dict[str, List[dict]] = {}
    for r in best_rows:
        by_model_best.setdefault(r["model"], []).append(r)
    with best_summary_csv.open("w", newline="", encoding="utf-8") as sf:
        sw = csv.DictWriter(sf, fieldnames=["model", *NUM_FIELDS])
        sw.writeheader()
        for model_name, rows in by_model_best.items():
            agg = {"model": model_name}
            for k in NUM_FIELDS:
                agg[k] = safe_mean([r.get(k) for r in rows])
            sw.writerow(agg)

    print(f"[OK] Wrote:\n  {jsonl_path}\n  {csv_path}\n  {summary_csv}\n  {best_summary_csv}")

if __name__ == "__main__":
    main()
