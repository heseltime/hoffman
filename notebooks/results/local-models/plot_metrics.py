#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

METRICS_UP   = ["bleu","rouge_l_f1","meteor","lr","ls"]  # higher is better
METRICS_DOWN = ["cer","wer"]                              # lower is better

def ensure_numeric(df):
    for col in METRICS_UP + METRICS_DOWN:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def save_bar(df, metric, outdir, title=None, lower_is_better=False, stem="avg"):
    d = df.sort_values(metric, ascending=lower_is_better)
    fig, ax = plt.subplots()
    ax.bar(d["model"], d[metric])
    ax.set_title(title or f"{stem} {metric}")
    ax.set_ylabel(metric)
    ax.set_xlabel("model")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = Path(outdir) / f"{stem}_{metric}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[OK] wrote {out}")

def save_scatter(df, x, y, outdir, title=None, stem=None):
    fig, ax = plt.subplots()
    for model, sub in df.groupby("model"):
        ax.scatter(sub[x], sub[y], label=model, alpha=0.7)
    ax.set_xlabel(x); ax.set_ylabel(y)
    ax.set_title(title or f"{y} vs {x}")
    ax.legend()
    plt.tight_layout()
    out = Path(outdir) / f"{stem or (y+'_vs_'+x)}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[OK] wrote {out}")

def save_box_by_model(df, metric, outdir, title=None, stem=None):
    groups = list(df.groupby("model"))
    data   = [g[1][metric].dropna().values for g in groups]
    labels = [g[0] for g in groups]
    fig, ax = plt.subplots()
    ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_title(title or f"{metric} by model (per response)")
    ax.set_ylabel(metric)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = Path(outdir) / f"{stem or (metric+'_box_by_model')}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[OK] wrote {out}")

def main():
    ap = argparse.ArgumentParser(description="Plot evaluation metrics.")
    ap.add_argument("--metrics", default="metrics.csv", help="metrics.csv (per response)")
    ap.add_argument("--summary", default="summary_by_model.csv", help="summary_by_model.csv (macro avg)")
    ap.add_argument("--docbest", default="summary_by_model_docbest.csv", help="best-per-doc summary")
    ap.add_argument("--outdir", default="plots", help="output folder for PNGs")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    # Per-response metrics
    df = pd.read_csv(args.metrics)
    df = ensure_numeric(df)

    # Averages
    if Path(args.summary).exists():
        avg = ensure_numeric(pd.read_csv(args.summary))
    else:
        # compute macro average if summary not present
        avg = df.groupby("model", as_index=False)[METRICS_UP + METRICS_DOWN].mean()

    # Best-per-doc summary
    best = None
    if Path(args.docbest).exists():
        best = ensure_numeric(pd.read_csv(args.docbest))

    # BARs: averages
    for m in METRICS_UP:
        if m in avg.columns:
            save_bar(avg, m, outdir, title=f"Model average {m}", lower_is_better=False, stem="avg")
    for m in METRICS_DOWN:
        if m in avg.columns:
            save_bar(avg, m, outdir, title=f"Model average {m} (lower is better)", lower_is_better=True, stem="avg")

    # BARs: best-per-doc (optional)
    if best is not None:
        for m in METRICS_UP:
            if m in best.columns:
                save_bar(best, m, outdir, title=f"Doc-best {m}", lower_is_better=False, stem="docbest")
        for m in METRICS_DOWN:
            if m in best.columns:
                save_bar(best, m, outdir, title=f"Doc-best {m} (lower is better)", lower_is_better=True, stem="docbest")

    # SCATTER: per-response BLEU vs LR (shows stochastic spread)
    if {"bleu","lr"}.issubset(df.columns):
        save_scatter(df, "bleu", "lr", outdir, title="Per-response BLEU vs LR", stem="scatter_bleu_vs_lr")

    # SCATTER: ROUGE-L vs METEOR
    if {"rouge_l_f1","meteor"}.issubset(df.columns):
        save_scatter(df, "rouge_l_f1", "meteor", outdir, title="Per-response ROUGE-L(F1) vs METEOR", stem="scatter_rougeL_vs_meteor")

    # BOXPLOTS: per-response distributions over models
    for m in ["bleu","rouge_l_f1","meteor","lr","ls"]:
        if m in df.columns:
            save_box_by_model(df, m, outdir, title=f"{m} by model (per response)")

if __name__ == "__main__":
    main()
