import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from collections import Counter



DN_LABEL_ORDER = [
    "ACB", "ASW", "BEB", "CDX", "CEUGBR",
    "CHB", "CHS", "CLM", "ESN", "FIN",
    "GIH", "GWD", "IBS", "JPT", "KHV",
    "LWK", "MSL", "MXL", "PEL", "PJL",
    "PUR", "STUITU", "TSI", "YRI",
]

label_order_1000G = ['YRI', 'ESN', 'GWD', 'LWK', 'MSL', 'ACB', 'ASW',
                     'IBS',  'CEUGBR', 'TSI', 'FIN',
                     'PJL', 'BEB', 'GIH', 'STUITU',
                     'CHB', 'CHS', 'CDX', 'KHV', 'JPT',
                     'MXL', 'CLM', 'PEL', 'PUR', ]
pop_colors=["#C7E9C0","#A1D99B","#74C476","#41AB5D","#238B45","#006D2C","#00441B",
            "#EFBBFF","#D896FF","#BE29EC","#800080",
            "#FEEDDE","#FDBE85","#FD8D3C","#E6550D",
            "#DEEBF7","#9ECAE1","#008080","#0ABAB5","#08519C",
           "#BC544B","#E3242B","#E0115F","#900D09",]
pop_palette = {label:color for label,color in zip(label_order_1000G, pop_colors)}


POP_RANK = {p: i for i, p in enumerate(DN_LABEL_ORDER)}


def pop_sort_key(pop):
    return POP_RANK.get(str(pop), len(DN_LABEL_ORDER))

def _vote_ranks_one_row(row_vals, m):
    u, c = np.unique(row_vals, return_counts=True)
    order = np.argsort(-c)
    u = u[order].astype(str)
    c = c[order].astype(np.float64)
    p = c / m
    return list(u), list(p)

def _sort_order_vote_mix(df_sub, mcols):
    vals = df_sub[mcols].to_numpy()
    n, m = vals.shape
    dominant = []
    maj_scores = np.empty(n)
    second_rank = np.zeros(n, dtype=np.int64)
    third_rank = np.zeros(n, dtype=np.int64)
    neg_second_p = np.zeros(n)
    neg_third_p = np.zeros(n)
    for i in range(n):
        pops, fr = _vote_ranks_one_row(vals[i], m)
        dominant.append(pops[0])
        maj_scores[i] = fr[0]
        if len(pops) > 1:
            neg_second_p[i] = -fr[1]
        if len(pops) > 2:
            neg_third_p[i] = -fr[2]
    win_counts = Counter(dominant)
    glob_order = [p for p, _ in win_counts.most_common()]
    glob_rank = {p: r for r, p in enumerate(glob_order)}
    def gr(name):
        return glob_rank.get(name, len(glob_order))
    for i in range(n):
        pops, _ = _vote_ranks_one_row(vals[i], m)
        if len(pops) > 1:
            second_rank[i] = gr(pops[1])
        if len(pops) > 2:
            third_rank[i] = gr(pops[2])
    dom_rank = np.array([glob_rank[d] for d in dominant], dtype=np.int64)
    samples = df_sub["samples"].astype(str).to_numpy()
    return np.lexsort(
        (
            samples,
            neg_third_p,
            third_rank,
            neg_second_p,
            second_rank,
            -maj_scores,
            dom_rank,
        )
    )
    
def model_columns(df):
    cols = [c for c in df.columns if c.startswith("model") and c[5:].isdigit()]
    return sorted(cols, key=lambda x: int(x.replace("model", "")))


def majority_fraction(row, mcols):
    vc = row[mcols].value_counts()
    return float(vc.iloc[0] / len(mcols))


def vote_proportions_matrix(df, mcols, pop_order):
    vals = df[mcols].to_numpy()
    n, m = vals.shape
    k = len(pop_order)
    pop_index = {str(p): i for i, p in enumerate(pop_order)}
    mat = np.zeros((n, k), dtype=np.float64)
    for i in range(n):
        u, c = np.unique(vals[i], return_counts=True)
        for pop, ct in zip(u, c):
            j = pop_index.get(str(pop))
            if j is not None:
                mat[i, j] = ct / m
    return mat


def plot_stacked_samples(df_sub, mcols, pop_order, colors, out_path, title):
    order = _sort_order_vote_mix(df_sub, mcols)
    df_ord = df_sub.iloc[order].reset_index(drop=True)
    mat = vote_proportions_matrix(df_ord, mcols, pop_order)
    n, k = mat.shape
    x = np.arange(n)
    fig_w = min(100.0, max(8.0, 0.028 * n))
    bar_w = min(0.9, 1.0 - 1e-3)
    fig, ax = plt.subplots(figsize=(fig_w, 6))
    bottom = np.zeros(n)
    for j, pop in enumerate(pop_order):
        h = mat[:, j]
        if h.max() == 0:
            continue
        ax.bar(x, h, bottom=bottom, width=bar_w, label=str(pop), color=colors[j])
        bottom = bottom + h
    ax.set_xticks(x)
    step = max(1, n // 40)
    tick_labels = [
        s if i % step == 0 else "" for i, s in enumerate(df_ord["samples"].astype(str))
    ]
    ax.set_xticklabels(tick_labels, rotation=90, fontsize=6)
    ax.set_xlim(-0.5, n - 0.5)
    ax.margins(x=0)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction of models")
    ax.set_xlabel("Sample (sorted by majority fraction, then population)")
    ax.set_title(title)
    ax.legend(
        ncol=min(6, k),
        loc="upper center",
        bbox_to_anchor=(0.5, 1.12),
        fontsize=7,
        frameon=False,
    )
    fig.subplots_adjust(top=0.82, bottom=0.18)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    args = parse_args()
    path = Path(args.predictions)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(path, sep="\t")
    mcols = model_columns(df)
    if len(mcols) != 15:
        raise SystemExit(f"Expected 15 model columns, found {len(mcols)}: {mcols}")

    maj = df.apply(lambda r: majority_fraction(r, mcols), axis=1)

    pops_present = sorted(
        [str(p) for p in pd.unique(df[mcols].to_numpy().ravel())],
        key=pop_sort_key,
    )
    colors = [pop_palette.get(p, "#808080") for p in pops_present]

    n_plot = len(df) if args.max_samples is None else min(args.max_samples, len(df))

    if args.selection == "first":
        idx = np.arange(n_plot)
    elif args.selection == "random":
        rng = np.random.default_rng(args.seed)
        idx = rng.choice(len(df), size=n_plot, replace=False)
        idx = np.sort(idx)
    else:
        idx = np.argsort(maj.values)[:n_plot]

    df_sub = df.iloc[idx].reset_index(drop=True)
    title = ""
    plot_stacked_samples(
        df_sub,
        mcols,
        pops_present,
        colors,
        out_dir / "dietnet_vote_mix_stacked.png",
        title,
    )

    print(f"Wrote figures under {out_dir.resolve()}")


def parse_args():
    p = argparse.ArgumentParser(
        description="Plot Dietnet ensemble vote percentages from *_dietnet_predictions.txt."
    )
    p.add_argument(
        "--predictions",
        type=str,
        required=True,
        help="Tab-separated predictions file (samples, model1..model15, all_models).",
    )
    p.add_argument(
        "--out-dir",
        type=str,
        default="dietnet_vote_plots",
        help="Directory for PNG outputs.",
    )
    p.add_argument(
        "--max-samples",
        type=int,
        default=None,
        metavar="N",
        help="Cap stacked bar plot to N samples; omit for all samples.",
    )
    p.add_argument(
        "--selection",
        choices=["first", "random", "uncertain"],
        default="uncertain",
        help="Which samples to include in the stacked bar plot.",
    )
    p.add_argument("--seed", type=int, default=0, help="RNG seed for --selection random.")
    return p.parse_args()


if __name__ == "__main__":
    main()