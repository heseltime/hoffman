#!/usr/bin/env python3
"""
rand_doc.py  –  create a .txt file and a stub PDF full of random tokens
                (use as a “no-overlap” baseline for BLEU/ROUGE/METEOR tests).

Usage:
    python rand_doc.py baseline 200     # 200 random words
"""
import random, string, sys
from pathlib import Path

VOCAB = [ ''.join(random.choices(string.ascii_lowercase, k=random.randint(3,8)))
          for _ in range(10_000) ]

def random_words(n):
    return ' '.join(random.choice(VOCAB) for _ in range(n))

def make_txt(stem, n):
    txt = random_words(n)
    Path(f"{stem}.txt").write_text(txt, encoding="utf-8")
    return txt

def make_pdf(stem, txt):
    # quick one-page PDF with text drawn at (50,750)
    stream = f"BT /F1 12 Tf 50 750 Td ({txt[:500].replace('(','\\(').replace(')','\\)')}) Tj ET"
    pdf = (
        "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        "   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj\n"
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        "xref\n0 6\n0000000000 65535 f \n"
        "0000000010 00000 n \n0000000060 00000 n \n0000000119 00000 n \n"
        "0000000275 00000 n \n0000000420 00000 n \n"
        "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n534\n%%EOF"
    )
    Path(f"{stem}.pdf").write_bytes(pdf.encode("latin-1"))

if __name__ == "__main__":
    stem = sys.argv[1]          # e.g. "baseline"
    n    = int(sys.argv[2])     # e.g. 200 words
    txt  = make_txt(stem, n)
    make_pdf(stem, txt)
    print(f"Wrote {stem}.txt and {stem}.pdf with {n} random words")
