#!/usr/bin/env python3
"""
evaluate_doc.py — Compare two documents with BLEU, ROUGE-L(F1), METEOR,
and edit-distance (raw + normalized).

Supports PDFs (two extraction modes) or plain-text files.

Usage
-----
  python evaluate_doc.py candidate.{pdf|txt} reference.{pdf|txt} \
         [--method {rendered,streams}] [--filter-pdfops] [--json]

Dependencies
------------
  pip install pdfminer.six pymupdf nltk rouge-score python-Levenshtein
  # optional fallback:
  pip install rapidfuzz
  python -m nltk.downloader punkt wordnet omw-1.4
"""
import argparse
import json
import logging
import math
import re
import sys
from collections import defaultdict
from bisect import bisect_right
from pathlib import Path
from typing import List

# ----------------------------- text extraction back-ends
try:
    from pdfminer.high_level import extract_text as _pdfminer_extract_text
except ImportError:
    _pdfminer_extract_text = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ----------------------------- NLP metrics
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer

# Reduce rouge-score chatter
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
try:
    import absl.logging as absl_logging
    absl_logging.set_verbosity("error")
except Exception:
    pass

_smooth = SmoothingFunction().method4
_tokeniser = re.compile(r"\w+")

# ----------------------------- Levenshtein backends (robust import)
def _char_lev_fallback(a: str, b: str) -> int:
    # memory-efficient DP
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins = curr[-1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]

try:
    import Levenshtein as _Lev
    def char_lev(a: str, b: str) -> int:
        return _Lev.distance(a, b)
except Exception:
    try:
        from rapidfuzz.distance import Levenshtein as _RLev
        def char_lev(a: str, b: str) -> int:
            return _RLev.distance(a, b)
    except Exception:
        char_lev = _char_lev_fallback

# ----------------------------- token helpers & filters
def _tokenise(text: str) -> List[str]:
    return _tokeniser.findall(text.lower())

PDF_OPS = {
    "m","l","c","v","y","h","re","S","s","f","F","f*","B","B*",
    "BT","ET","Td","Tm","Tj","TJ","Tf","Tc","TL","Tr","Ts","Tw","T*"
}
NUM = re.compile(r"^-?\d+(?:\.\d+)?$")

def _tokenise_filtered(text: str) -> List[str]:
    toks = _tokenise(text)
    return [t for t in toks if t not in PDF_OPS and not NUM.match(t)]

def _edit_distance_seq(a: List[str], b: List[str]) -> int:
    na, nb = len(a), len(b)
    if na == 0:
        return nb
    if nb == 0:
        return na
    prev = list(range(nb + 1))
    for i, x in enumerate(a, 1):
        curr = [i]
        for j, y in enumerate(b, 1):
            cost = 0 if x == y else 1
            curr.append(min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            ))
        prev = curr
    return prev[-1]

def _safe_div(n: float, d: float):
    return (n / d) if d not in (0, 0.0) else None  # JSON-safe (no inf/NaN)

# ----------------------------- simple METEOR fallback on tokens
def _meteor_fallback_tokens(ref_tokens: List[str], hyp_tokens: List[str]) -> float:
    """
    METEOR approximation with exact token matches:
      F_mean = 10PR / (R + 9P), Pen = 0.5 * (ch/m)^3, METEOR = F_mean * (1 - Pen)
    Uses greedy monotonic alignment to count chunks.
    """
    if not ref_tokens or not hyp_tokens:
        return 0.0
    # positions of each token in ref
    pos = defaultdict(list)
    for i, t in enumerate(ref_tokens):
        pos[t].append(i)

    matched_positions = []
    last = -1
    # per-token pointer to next usable position (to keep monotonicity)
    ptr = {t:0 for t in pos}
    for t in hyp_tokens:
        if t not in pos:
            continue
        lst = pos[t]
        k = bisect_right(lst, last, lo=ptr[t])  # first position > last
        if k < len(lst):
            matched_positions.append(lst[k])
            last = lst[k]
            ptr[t] = k + 1

    m = len(matched_positions)
    if m == 0:
        return 0.0
    P = m / len(hyp_tokens)
    R = m / len(ref_tokens)
    F = (10 * P * R) / (R + 9 * P) if (P + R) > 0 else 0.0

    # chunks: consecutive positions form one chunk
    ch = 0
    prev = None
    for p in matched_positions:
        if prev is None or p != prev + 1:
            ch += 1
        prev = p
    Pen = 0.5 * (ch / m) ** 3
    return F * (1 - Pen)

# ----------------------------- metric core
def _compute_metrics(ref: str, hyp: str, *, filtered: bool):
    # tokenization (optionally filtered for PDF operators/numbers)
    if filtered:
        ref_tokens = _tokenise_filtered(ref)
        hyp_tokens = _tokenise_filtered(hyp)
    else:
        ref_tokens = _tokenise(ref)
        hyp_tokens = _tokenise(hyp)

    metrics = {}

    # BLEU (sentence-level with smoothing)
    try:
        metrics["bleu"] = sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=_smooth)
        logging.info("BLEU: %.4f", metrics["bleu"])
    except Exception as e:
        logging.warning("BLEU failed: %s", e);  metrics["bleu"] = None

    # ROUGE-L (F1) on tokenized strings to keep tokenizer consistent
    try:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        rouge_l_f1 = scorer.score(" ".join(ref_tokens), " ".join(hyp_tokens))["rougeL"].fmeasure
        metrics["rouge_l_f1"] = rouge_l_f1
        metrics["rouge_l"] = rouge_l_f1  # alias for backward-compat
        logging.info("ROUGE-L(F1): %.4f", rouge_l_f1)
    except Exception as e:
        logging.warning("ROUGE failed: %s", e);  metrics["rouge_l_f1"] = metrics["rouge_l"] = None

    # METEOR — try tokenized API first, then string API, then our fallback
    meteor = None
    try:
        meteor = meteor_score([ref_tokens], hyp_tokens)  # newer NLTK expects Iterable[str]
    except Exception:
        try:
            meteor = meteor_score([' '.join(ref_tokens)], ' '.join(hyp_tokens))  # older NLTK expects str
        except Exception as e:
            logging.warning("METEOR (NLTK) failed: %s; using fallback.", e)
            try:
                meteor = _meteor_fallback_tokens(ref_tokens, hyp_tokens)
            except Exception as ee:
                logging.warning("METEOR fallback failed: %s", ee)
                meteor = None
    metrics["meteor"] = meteor
    if meteor is not None:
        logging.info("METEOR: %.4f", meteor)

    # Edit distances (chars + tokens)
    try:
        d_char = char_lev(ref, hyp)
    except Exception as e:
        logging.warning("Char Levenshtein failed: %s", e); d_char = None
    try:
        d_tok = _edit_distance_seq(ref_tokens, hyp_tokens)
    except Exception as e:
        logging.warning("Token Levenshtein failed: %s", e); d_tok = None

    # Lengths
    len_r_chars = len(ref)
    len_c_chars = len(hyp)
    len_r_tok = len(ref_tokens)
    len_c_tok = len(hyp_tokens)

    # Normalized edit metrics (JSON-safe)
    cer = _safe_div(d_char, len_r_chars) if d_char is not None else None
    wer = _safe_div(d_tok, len_r_tok) if d_tok is not None else None
    ls_div = _safe_div(d_char, max(len_r_chars, len_c_chars)) if d_char is not None else None
    ls  = (1.0 - ls_div) if ls_div is not None else None
    lr  = _safe_div(len_r_chars + len_c_chars - d_char, len_r_chars + len_c_chars) if d_char is not None else None

    # Dashboard fields
    metrics.update({
        "edit_distance_chars": d_char,
        "edit_distance_tokens": d_tok,
        "cer": cer,   # Character Error Rate (lower is better)
        "wer": wer,   # Token/Word Error Rate (lower is better)
        "ls": ls,     # Levenshtein Similarity (higher is better)
        "lr": lr,     # Levenshtein Ratio (higher is better)
        "ref_length_chars": len_r_chars,
        "hyp_length_chars": len_c_chars,
        "ref_length_tokens": len_r_tok,
        "hyp_length_tokens": len_c_tok,
    })

    return metrics

# ----------------------------- extraction routines
def _extract_rendered(pdf: Path) -> str:
    if _pdfminer_extract_text is None:
        sys.exit("pdfminer.six not installed; cannot use rendered mode.")
    try:
        return _pdfminer_extract_text(str(pdf))
    except Exception as e:
        logging.error("pdfminer failed on %s: %s", pdf, e)
        return ""

def _extract_streams(pdf: Path) -> str:
    if fitz is None:
        sys.exit("PyMuPDF not installed; cannot use streams mode.")
    try:
        doc = fitz.open(pdf)
        buf = []
        for page in doc:
            xrefs = page.get_contents()
            if not xrefs:
                continue
            raw = b"".join(doc.xref_stream(x) for x in xrefs)
            buf.append(raw.decode("utf-8", "ignore"))
        return "\n".join(buf)
    except Exception as e:
        logging.error("PyMuPDF failed on %s: %s", pdf, e)
        return ""

def _extract_text(path: Path, method: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        if method == "rendered":
            return _extract_rendered(path)
        if method == "streams":
            return _extract_streams(path)
        sys.exit(f"Unknown extraction method: {method}")
    # unknown extension → treat as plain text
    return path.read_text(encoding="utf-8", errors="ignore")

# ----------------------------- CLI
def main():
    p = argparse.ArgumentParser(description="BLEU/ROUGE-L(F1)/METEOR + edit-distance for PDF/TXT.")
    p.add_argument("candidate", type=Path)
    p.add_argument("reference", type=Path)
    p.add_argument("--method", choices=["rendered","streams"], default="rendered",
                   help="How to extract text from PDFs (default: rendered).")
    p.add_argument("--filter-pdfops", action="store_true",
                   help="Ignore PDF graphics operators & numbers during tokenisation.")
    p.add_argument("--json", action="store_true", help="Output JSON.")
    args = p.parse_args()

    cand = _extract_text(args.candidate, args.method)
    ref  = _extract_text(args.reference,  args.method)

    if not cand.strip():
        sys.exit("No text extracted from candidate.")
    if not ref.strip():
        sys.exit("No text extracted from reference.")

    metrics = _compute_metrics(ref, cand, filtered=args.filter_pdfops)

    # Always JSON if requested; otherwise compact human-readable dashboard
    if args.json:
        print(json.dumps({
            "file_reference": str(args.reference),
            "file_candidate": str(args.candidate),
            "extraction_method": args.method,
            "filter_pdfops": args.filter_pdfops,
            **metrics
        }, indent=2))
    else:
        def f4(x):
            try: return f"{x:.4f}"
            except: return str(x)
        print("=== Similarity (overlap) ===")
        print(f"BLEU: {f4(metrics['bleu'])}  ROUGE-L(F1): {f4(metrics['rouge_l_f1'])}  METEOR: {f4(metrics['meteor'])}")
        print("=== Edit-based (normalized) ===")
        print(f"LR: {f4(metrics['lr'])}  LS: {f4(metrics['ls'])}  CER: {f4(metrics['cer'])}  WER: {f4(metrics['wer'])}")
        print("=== Distances & Lengths ===")
        print(f"edit_distance_chars: {metrics['edit_distance_chars']}  edit_distance_tokens: {metrics['edit_distance_tokens']}")
        print(f"chars R/H: {metrics['ref_length_chars']} / {metrics['hyp_length_chars']}  "
              f"tokens R/H: {metrics['ref_length_tokens']} / {metrics['hyp_length_tokens']}")

if __name__ == "__main__":
    main()
