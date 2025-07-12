
#!/usr/bin/env python3
"""evaluate_pdf.py

Command‑line tool to compare an LLM‑generated “accessible” PDF against a
ground‑truth reference PDF using common text‑similarity metrics:
  • BLEU
  • ROUGE‑L
  • METEOR
  • Levenshtein (edit) distance

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
    """Lower‑case word tokens (alphanumerics)."""
    return _tokeniser.findall(text.lower())


def compute_metrics(ref: str, hyp: str):
    ref_tokens = tokenise(ref)
    hyp_tokens = tokenise(hyp)

    bleu = sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=_smooth)

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rouge_l = scorer.score(ref, hyp)["rougeL"].fmeasure

    meteor = meteor_score([ref], hyp)

    edit_distance = Levenshtein.distance(ref, hyp)

    return {
        "bleu": bleu,
        "rouge_l": rouge_l,
        "meteor": meteor,
        "edit_distance": edit_distance,
        "ref_length_chars": len(ref),
        "hyp_length_chars": len(hyp),
    }


def extract_pdf_text(path: Path) -> str:
    """Return all text extracted from a PDF file."""
    try:
        return extract_text(str(path))
    except Exception as exc:
        print(f"[ERROR] Failed to read {path}: {exc}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(description="Evaluate accessible‑PDF transformation quality.")
    parser.add_argument("predicted", type=Path, help="LLM‑generated PDF")
    parser.add_argument("reference", type=Path, help="Ground‑truth accessible PDF")
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
    else:
        for k, v in metrics.items():
            if k.endswith("_distance") or k.endswith("_chars"):
                print(f"{k:15}: {v}")
            else:
                print(f"{k:15}: {v:.4f}")


if __name__ == "__main__": 
    main()
