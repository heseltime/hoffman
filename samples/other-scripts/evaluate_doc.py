#!/usr/bin/env python3
"""
evaluate_doc.py  —  Compare two documents with BLEU, ROUGE-L, METEOR, edit-distance.

Supports PDFs (two extraction modes) or plain-text files.

Usage
-----
  python evaluate_doc.py candidate.{pdf|txt} reference.{pdf|txt} \
         [--method {rendered,streams}] [--filter-pdfops] [--json]

Dependencies
------------
  pip install pdfminer.six pymupdf nltk rouge-score python-Levenshtein
  python -m nltk.downloader punkt wordnet omw-1.4
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import List

# ------------------------------------------------------------------ text extraction back-ends
try:
    from pdfminer.high_level import extract_text as _pdfminer_extract_text
except ImportError:
    _pdfminer_extract_text = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ------------------------------------------------------------------ NLP metrics
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer
import Levenshtein

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_smooth = SmoothingFunction().method4
_tokeniser = re.compile(r"\w+")

# ------------------------------------------------------------------ token helpers & filters
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

# ------------------------------------------------------------------ metric core
def _compute_metrics(ref: str, hyp: str, *, filtered: bool):
    if filtered:
        ref_tokens = _tokenise_filtered(ref)
        hyp_tokens = _tokenise_filtered(hyp)
    else:
        ref_tokens = _tokenise(ref)
        hyp_tokens = _tokenise(hyp)

    metrics = {}
    # BLEU
    try:
        metrics["bleu"] = sentence_bleu([ref_tokens], hyp_tokens,
                                        smoothing_function=_smooth)
        logging.info("BLEU: %.4f", metrics["bleu"])
    except Exception as e:
        logging.warning("BLEU failed: %s", e);  metrics["bleu"] = None
    # ROUGE-L
    try:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        metrics["rouge_l"] = scorer.score(ref, hyp)["rougeL"].fmeasure
        logging.info("ROUGE-L: %.4f", metrics["rouge_l"])
    except Exception as e:
        logging.warning("ROUGE failed: %s", e);  metrics["rouge_l"] = None
    # METEOR
    try:
        try:
            meteor = meteor_score([ref_tokens], hyp_tokens)
        except TypeError:  # older NLTK
            meteor = meteor_score([' '.join(ref_tokens)], ' '.join(hyp_tokens))
        metrics["meteor"] = meteor
        logging.info("METEOR: %.4f", meteor)
    except Exception as e:
        logging.warning("METEOR failed: %s", e); metrics["meteor"] = None
    # Edit distance
    try:
        metrics["edit_distance"] = Levenshtein.distance(ref, hyp)
        logging.info("Edit-distance: %d", metrics["edit_distance"])
    except Exception as e:
        logging.warning("Levenshtein failed: %s", e); metrics["edit_distance"] = None

    metrics["ref_length_chars"] = len(ref)
    metrics["hyp_length_chars"] = len(hyp)
    return metrics

# ------------------------------------------------------------------ extraction routines
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

# ------------------------------------------------------------------ CLI
def main():
    p = argparse.ArgumentParser(description="BLEU/ROUGE/METEOR/edit-distance for PDF/TXT.")
    p.add_argument("candidate", type=Path)
    p.add_argument("reference", type=Path)
    p.add_argument("--method", choices=["rendered","streams"], default="rendered",
                   help="How to extract text from PDFs (default: rendered).")
    p.add_argument("--filter-pdfops", action="store_true",
                   help="Ignore graphics operators & numbers when tokenising.")
    p.add_argument("--json", action="store_true", help="Output JSON.")
    args = p.parse_args()

    cand = _extract_text(args.candidate, args.method)
    ref  = _extract_text(args.reference,  args.method)

    if not cand.strip():
        sys.exit("No text extracted from candidate.")
    if not ref.strip():
        sys.exit("No text extracted from reference.")

    m = _compute_metrics(ref, cand, filtered=args.filter_pdfops)
    print(json.dumps(m, indent=2) if args.json
          else "\n".join(f"{k:18}: {v:.4f}" if isinstance(v, float) else f"{k:18}: {v}"
                         for k,v in m.items()))

if __name__ == "__main__":
    main()
