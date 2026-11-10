import argparse
import numpy as np
import pandas as pd
import h5py
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from population_config import (
    dn_label_order,
    pop_to_continent,
    pop_palette,
    continent_palette)


def main():
    args = parse_args()

    # Last hidden layer size
    LHL_SIZE=100

    # Load 1KGP samples and pop labels from hdf5
    with h5py.File(args.kgp_hdf5, 'r') as f:
        kgp_samples = [i.decode() for i in f['samples']]
        kgp_labels = [f['class_label_names'][int(i)].decode() for i in f['class_labels']]
    
    # Load samples from user-uploaded hdf5
    with h5py.File(args.user_hdf5, 'r') as f:
        user_samples = [i.decode() for i in f['samples']]

    # Load last hidden layer
    nb_models = args.folds * args.reps
    kgp_lhl = np.zeros((len(kgp_samples), nb_models*LHL_SIZE))
    user_lhl = np.zeros((len(user_samples), nb_models*LHL_SIZE))

    j = 0
    for fold in range(1, args.folds+1):
        for rep in range(1, args.reps+1):
            # 1KGP lhl
            kgp_model_res = np.load(
                args.kgp_model_output.format(fold=fold,rep=rep),
                allow_pickle=True)
            kgp_lhl[:,j:j+LHL_SIZE] = kgp_model_res['last_hidden_layer']

            # User uploaded samples lhl
            user_model_res = np.load(
                args.user_model_output.format(fold=fold,rep=rep),
                allow_pickle=True
            )
            user_lhl[:,j:j+LHL_SIZE] = user_model_res['last_hidden_layer']

            j+=LHL_SIZE


    # Compute PCA
    N_COMPONENTS=2

    # Fit PCA on 1KGP data (and transform to get 1KPG samples pc values)
    pca = PCA(N_COMPONENTS)
    kgp_pca = pca.fit_transform(kgp_lhl)

    # Project user samples
    user_proj = pca.transform(user_lhl)

    # Put PCA results in dataframe
    kgp_df = pd.DataFrame(kgp_pca, columns=[f'PC{i+1}' for i in range(N_COMPONENTS)])
    kgp_df.insert(0, 'Samples', kgp_samples)
    kgp_df['Pop_label'] = kgp_labels

    user_df = pd.DataFrame(user_proj, columns=[f'PC{i+1}' for i in range(N_COMPONENTS)])
    user_df.insert(0, 'Samples', user_samples)

    # Plot
    kgp_marker="o"
    user_marker = "^"

    fig_pop, ax_pop = plt.subplots(figsize=(6, 6))
    fig_continent, ax_continent = plt.subplots(figsize=(6, 6))

    # Define colors : dataset labels for 1KGP, most voted label for user predictions
    kgp_pop_colors = [pop_palette[i] for i in kgp_df['Pop_label']]
    kgp_continent_colors = [continent_palette[pop_to_continent[i]] for i in kgp_df['Pop_label']]

    user_compiled_preds = pd.read_csv(args.user_compiled_predictions, sep='\t').fillna('None')
    user_df_merge = pd.merge(user_df, user_compiled_preds, on='Samples')
    user_pop_colors = [pop_palette[i] for i in user_df_merge['Most_voted_population']]
    user_continent_colors = [continent_palette[i] for i in user_df_merge['Most_voted_continent']]

    # Make the scatter plots
    ax_pop.scatter(kgp_df['PC1'], kgp_df['PC2'], marker=kgp_marker, facecolors='none', edgecolors=kgp_pop_colors)
    ax_pop.scatter(user_df_merge['PC1'], user_df_merge['PC2'], marker=user_marker, facecolors='none', edgecolors=user_pop_colors)

    ax_continent.scatter(kgp_df['PC1'], kgp_df['PC2'], marker=kgp_marker, facecolors='none', edgecolors=kgp_continent_colors)
    ax_continent.scatter(user_df_merge['PC1'], user_df_merge['PC2'], marker=user_marker, facecolors='none', edgecolors=user_continent_colors)

    # Legends
    handles = [
    Patch(facecolor=color, label=population)
    for population, color in pop_palette.items()
    ]

    marker_handles = [
    Line2D([], [], markerfacecolor="none", markeredgecolor="black", marker="o", linestyle="None",
           markersize=8, label="1KGP"),
    Line2D([], [], markerfacecolor="none", markeredgecolor="black", marker="^", linestyle="None",
           markersize=8, label=args.output),
    ]

    handles += marker_handles

    ax_pop.legend(
        handles=handles,
        title="Population",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
        fontsize=8
    )
    
    handles = [
    Patch(facecolor=color, label=continent)
    for continent, color in continent_palette.items()
    ]

    handles += marker_handles

    ax_continent.legend(
        handles=handles,
        title="Continent",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
    )

    # Axes labels
    for ax in [ax_pop, ax_continent]:
        ax.set_xlabel("PC1 (last hidden layer)")
        ax.set_ylabel("PC2 (last hidden layer)")


    # Save figures
    fig_pop.savefig('{}_representation_pop.png'.format(args.output), bbox_inches="tight",pad_inches=0.15,dpi=300)
    fig_continent.savefig('{}_representation_continent.png'.format(args.output), bbox_inches="tight",pad_inches=0.15,dpi=300)



def parse_args():
    parser = argparse.ArgumentParser(description="Hidden Layer PCA")
    parser.add_argument(
        "--kgp-hdf5",
        required=True,
        help="1KGP hdf5 file. Provide full path."
    )
    parser.add_argument(
        "--kgp-model-output",
        required=True,
        help="1KGP results npz file returned by each model. Provide full path.")

    parser.add_argument(
        "--user-hdf5",
        required=True,
        help="Hdf5 file of user-uploaded dataset. Provide full path."
    )
    parser.add_argument(
        "--user-model-output",
        required=True,
        help="Results npz file returned by each model for user-uploaded data. Provide full path.")

    parser.add_argument(
        "--user-compiled-predictions",
        required=True,
        help="Result txt file with compiled predictions across models (most voted label). Provide full path.")

    parser.add_argument(
        "--folds",
        required=True,
        type=int,
        help="Number of folds (numbered from 1)"
    )
    
    parser.add_argument(
        "--reps",
        required=True,
        type=int,
        help="Number of repetitions or seeds (numbered from 1).",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output name."
    )

    return parser.parse_args()

if __name__=="__main__":
    main()