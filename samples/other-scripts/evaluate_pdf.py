#!/usr/bin/env python3
"""evaluate_pdf.py

Command-line tool to compare an LLM-generated “accessible” PDF against a
ground-truth reference PDF using common text-similarity metrics:
  • BLEU
  • ROUGE-L (F1)
  • METEOR
  • Levenshtein (edit) distance
  • Length-normalized edit metrics: CER, WER, LR, LS

Example
-------
python evaluate_pdf.py transformed.pdf reference.pdf --json

Dependencies
------------
pip install pdfminer.six nltk rouge-score python-Levenshtein

NLTK data required for METEOR:
>>> python -m nltk.downloader punkt wordnet omw-1.4
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import List

# PDF text extraction
from pdfminer.high_level import extract_text

# Metrics
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer
import Levenshtein

_smooth = SmoothingFunction().method4
_tokeniser = re.compile(r"\w+")


def tokenise(text: str) -> List[str]:
    """Lower-case word tokens (alphanumerics)."""
    return _tokeniser.findall(text.lower())


def edit_distance_seq(a: List[str], b: List[str]) -> int:
    """Levenshtein distance for token sequences using a memory-efficient DP."""
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
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost  # substitution
            ))
        prev = curr
    return prev[-1]


def safe_div(numer: float, denom: float, fallback: float = math.nan) -> float:
    return numer / denom if denom != 0 else fallback


def compute_metrics(ref: str, hyp: str):
    # Tokenize
    ref_tokens = tokenise(ref)
    hyp_tokens = tokenise(hyp)

    # BLEU (sentence-level with smoothing)
    bleu = sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=_smooth)

    # ROUGE-L (F1)
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rouge_l_f1 = scorer.score(ref, hyp)["rougeL"].fmeasure

    # METEOR
    meteor = meteor_score([ref], hyp)

    # Edit distances
    d_char = Levenshtein.distance(ref, hyp)
    d_tok = edit_distance_seq(ref_tokens, hyp_tokens)

    # Lengths
    len_r_chars = len(ref)
    len_c_chars = len(hyp)
    len_r_tok = len(ref_tokens)
    len_c_tok = len(hyp_tokens)

    # Normalized edit metrics
    cer = safe_div(d_char, len_r_chars, fallback=math.inf)  # char error rate
    wer = safe_div(d_tok, len_r_tok, fallback=math.inf)     # word/token error rate

    # Similarities in [0,1]
    # LS = 1 - d / max(|R|,|C|)
    ls = 1.0 - safe_div(d_char, max(len_r_chars, len_c_chars, 1))
    # LR = (|R| + |C| - d) / (|R| + |C|)
    lr = safe_div(len_r_chars + len_c_chars - d_char, len_r_chars + len_c_chars, fallback=1.0 if (len_r_chars + len_c_chars) == 0 else math.nan)

    return {
        # Overlap-based metrics
        "bleu": bleu,
        "rouge_l_f1": rouge_l_f1,
        "meteor": meteor,

        # Edit distances (raw)
        "edit_distance_chars": d_char,
        "edit_distance_tokens": d_tok,

        # Normalized edit metrics
        "cer": cer,
        "wer": wer,
        "ls": ls,
        "lr": lr,

        # Lengths
        "ref_length_chars": len_r_chars,
        "hyp_length_chars": len_c_chars,
        "ref_length_tokens": len_r_tok,
        "hyp_length_tokens": len_c_tok,

        # Backward-compat alias (ROUGE-L as 'rouge_l')
        "rouge_l": rouge_l_f1,
    }


def extract_pdf_text(path: Path) -> str:
    """Return all text extracted from a PDF file."""
    try:
        return extract_text(str(path))
    except Exception as exc:
        print(f"[ERROR] Failed to read {path}: {exc}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(description="Evaluate accessible-PDF transformation quality.")
    parser.add_argument("predicted", type=Path, help="LLM-generated PDF")
    parser.add_argument("reference", type=Path, help="Ground-truth accessible PDF")
    parser.add_argument("--json", action="store_true", help="Print metrics as JSON")
    args = parser.parse_args()

    pred_text = extract_pdf_text(args.predicted)
    ref_text = extract_pdf_text(args.reference)

    if not pred_text.strip():
        sys.exit("No text extracted from predicted PDF.")
    if not ref_text.strip():
        sys.exit("No text extracted from reference PDF.")

    metrics = compute_metrics(ref_text, pred_text)

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    # Human-readable compact dashboard
    def f4(x):
        try:
            return f"{x:.4f}"
        except Exception:
            return str(x)

    print("=== Similarity Metrics ===")
    print(f"BLEU: {f4(metrics['bleu'])}  "
          f"ROUGE-L(F1): {f4(metrics['rouge_l_f1'])}  "
          f"METEOR: {f4(metrics['meteor'])}")

    print("=== Edit-based (normalized) ===")
    print(f"LR: {f4(metrics['lr'])}  "
          f"LS: {f4(metrics['ls'])}  "
          f"CER: {f4(metrics['cer'])}  "
          f"WER: {f4(metrics['wer'])}")

    print("=== Distances and Lengths ===")
    print(f"edit_distance_chars: {metrics['edit_distance_chars']}  "
          f"edit_distance_tokens: {metrics['edit_distance_tokens']}")
    print(f"chars R/H: {metrics['ref_length_chars']} / {metrics['hyp_length_chars']}  "
          f"tokens R/H: {metrics['ref_length_tokens']} / {metrics['hyp_length_tokens']}")


if __name__ == "__main__":
    main()
