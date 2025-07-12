#!/usr/bin/env python3
"""
plot_metrics.py  – Visualise BLEU / ROUGE-L / METEOR from evaluate_doc.py.

Typical use-cases
-----------------
# 1) Pipe a single run straight in
evaluate_doc.py out.pdf ref.pdf --json | python plot_metrics.py

# 2) Plot several JSON files at once
python plot_metrics.py run1.json run2.json run3.json
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def load_results(paths_or_stdin):
    """Yield (label, metrics_dict) pairs."""
    if paths_or_stdin:                              # file(s) on CLI
        for p in paths_or_stdin:
            data = json.loads(Path(p).read_text())
            yield Path(p).stem, data
    else:                                           # piped via stdin
        stdin_data = sys.stdin.read().strip()
        if not stdin_data:
            sys.exit("No JSON on stdin.")
        yield "run", json.loads(stdin_data)


def main():
    parser = argparse.ArgumentParser(description="Plot BLEU/ROUGE/METEOR bars.")
    parser.add_argument("files", nargs="*", help="JSON files from evaluate_doc.py")
    args = parser.parse_args()

    runs = list(load_results(args.files))

    # ── Bar chart for BLEU / ROUGE-L / METEOR ───────────────────────
    metrics = ["bleu", "rouge_l", "meteor"]
    x = range(len(metrics))
    bar_width = 0.8 / len(runs)            # space multiple runs side-by-side

    for idx, (label, data) in enumerate(runs):
        vals = [data.get(m, 0) or 0 for m in metrics]
        plt.bar([i + idx * bar_width for i in x], vals,
                bar_width, label=label)    # no colour argument → default palette

        # Print non-plotted values so you don’t lose them
        print(f"{label:15}  edit_distance={data.get('edit_distance'):<6}  "
              f"ref_len={data.get('ref_length_chars')}  "
              f"hyp_len={data.get('hyp_length_chars')}")

    plt.xticks([i + bar_width*(len(runs)-1)/2 for i in x], metrics)
    plt.ylabel("Score")
    plt.title("Text-similarity metrics")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
