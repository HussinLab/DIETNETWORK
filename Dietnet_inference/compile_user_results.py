#!/bin/bash
import argparse
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def main():
    # Correspondance between model output (int) and population labels
    dn_label_order = ['ACB', 'ASW', 'BEB', 'CDX', 'CEUGBR',
                      'CHB', 'CHS', 'CLM', 'ESN', 'FIN',
                      'GIH', 'GWD', 'IBS', 'JPT', 'KHV',
                      'LWK', 'MSL', 'MXL', 'PEL', 'PJL',
                      'PUR', 'STUITU', 'TSI', 'YRI']

    # Correspondance between population labels and continent labels
    pop_to_continent = {
        'ACB': 'AFR',
        'ASW': 'AFR',
        'BEB': 'SAS',
        'CDX': 'EAS',
        'CEUGBR': 'EUR',
        'CHB': 'EAS',
        'CHS': 'EAS',
        'CLM': 'AMR',
        'ESN': 'AFR',
        'FIN': 'EUR',
        'GIH': 'SAS',
        'GWD': 'AFR',
        'IBS': 'EUR',
        'JPT': 'EAS',
        'KHV': 'EAS',
        'LWK': 'AFR',
        'MSL': 'AFR',
        'MXL': 'AMR',
        'PEL': 'AMR',
        'PJL': 'SAS',
        'PUR': 'AMR',
        'STUITU': 'SAS',
        'TSI': 'EUR',
        'YRI': 'AFR'
    }

    # Population colors for plotting
    color_order = ['YRI', 'ESN', 'GWD', 'LWK', 'MSL', 'ACB', 'ASW',
                   'IBS',  'CEUGBR', 'TSI', 'FIN',
                   'PJL', 'BEB', 'GIH', 'STUITU',
                   'CHB', 'CHS', 'CDX', 'KHV', 'JPT',
                   'MXL', 'CLM', 'PEL', 'PUR',
                   'None']

    pop_colors = ["#C7E9C0","#A1D99B","#74C476","#41AB5D","#238B45","#006D2C","#00441B",
                    "#EFBBFF","#D896FF","#BE29EC","#800080",
                    "#FEEDDE","#FDBE85","#FD8D3C","#E6550D",
                    "#DEEBF7","#9ECAE1","#008080","#0ABAB5","#08519C",
                    "#BC544B","#E3242B","#E0115F","#900D09",
                    "#808080"]

    pop_palette = {label:color for label,color in zip(color_order, pop_colors)}

    # Continent colors for plotting
    continent_palette = {
    'AFR': '#238B45',  # Green
    'EUR': '#BE29EC',  # Purple
    'SAS': '#FDBE85',  # Light orange
    'EAS': '#08519C',  # Deep blue
    'AMR': '#E3242B',   # Red
    'None': '#808080'  # Gray
    }
    
    args = parse_args()
    
    # Load results for all models
    samples = []
    res_bymodel = []

    for fold in range(1,args.folds+1):
        for rep in range(1,args.reps+1):
            # Load results for this model
            model_results = np.load(args.dietnet_results.format(fold=fold, rep=rep))
            
            if len(samples) == 0:
                samples = model_results['samples']
                
            res_bymodel.append(model_results['preds'].astype(np.int8))

    # Put the results in a dataframe with cols names 'model1' to 'modelN'
    res_df = pd.DataFrame({'Samples': samples})
    for i in range(len(res_bymodel)):
        res_df['model{}'.format(i+1)] = res_bymodel[i]

    # Map preds (int) to population and continent labels
    for col in res_df.columns:
        if col.startswith('model'):
            # Population labels
            res_df[col] = res_df[col].apply(lambda x: dn_label_order[x])
            # Continent labels
            res_df[col+'_continent'] = res_df[col].apply(lambda x: pop_to_continent[x])

    # Add columns for counts of each predicted population and continent across all models
    predicted_populations = []
    predicted_continents = []
    mostvoted_populations = []
    mostvoted_continents = []
    for i,row in res_df.iterrows():
        pop_counts = Counter(row[[col for col in res_df.columns if col.startswith('model') and not col.endswith('_continent')]].values)
        continent_counts = Counter(row[[col for col in res_df.columns if col.startswith('model') and col.endswith('_continent')]].values)

        pop_counts_sorted = pop_counts.most_common()
        continent_counts_sorted = continent_counts.most_common()

        predicted_populations.append(','.join([f'{pop}({count})' for pop, count in pop_counts_sorted]))
        predicted_continents.append(','.join([f'{continent}({count})' for continent, count in continent_counts_sorted]))

        if pop_counts_sorted[0][1] >= args.pop_threshold:
            mostvoted_populations.append(pop_counts_sorted[0][0])
        else:
            mostvoted_populations.append('None')

        if continent_counts_sorted[0][1] >= args.continent_threshold:
            mostvoted_continents.append(continent_counts_sorted[0][0])
        else:
            mostvoted_continents.append('None')

    res_df['All_predicted_populations'] = predicted_populations
    res_df['All_predicted_continents'] = predicted_continents
    res_df['Most_voted_population'] = mostvoted_populations
    res_df['Most_voted_continent'] = mostvoted_continents

    # Add samples missingness
    miss = pd.read_csv(args.sample_missingness, sep=r'\s+')[['IID', 'F_MISS']]
    res_df = res_df.merge(miss, left_on='Samples', right_on='IID')
    
    # Save df of results to file
    summary_df = res_df[['Samples', 'F_MISS', 'Most_voted_continent', 'Most_voted_population', 'All_predicted_continents','All_predicted_populations']]
    summary_df.to_csv(args.out+"_predictions.txt", index=False, sep='\t')

    pop_df = res_df[['Samples', 'F_MISS']+[col for col in res_df.columns if col.startswith('model') and not col.endswith('_continent')]]
    pop_df.to_csv(args.out+"_predictions_bymodel_population.txt", index=False, sep='\t')
    
    continent_df = res_df[['Samples', 'F_MISS']+[col for col in res_df.columns if col.startswith('model') and col.endswith('_continent')]].copy()
    continent_df.rename(columns={col: col.replace('_continent','') for col in continent_df.columns if col.startswith('model')}, inplace=True)
    continent_df.to_csv(args.out+"_predictions_bymodel_continent.txt", index=False, sep='\t')

    # Plotting the distribution of predicted populations across all samples
    plot_results_population(res_df, pop_palette, continent_palette, args.out)


def plot_results_population(res_df, pop_palette, continent_palette, outfile):
    pop_rank = {'YRI': 0, 'ESN': 1, 'GWD': 2, 'LWK': 3, 'MSL': 4, 'ACB': 5, 'ASW': 6,
                'IBS': 7, 'CEUGBR': 8, 'TSI': 9, 'FIN': 10,
                'PJL': 11, 'BEB': 12, 'GIH': 13, 'STUITU': 14,
                'CHB': 15, 'CHS': 16, 'CDX': 17, 'KHV': 18, 'JPT': 19,
                'MXL': 20, 'CLM': 21, 'PEL': 22, 'PUR': 23}
    
    continent_rank = {'AFR': 0, 'EUR': 1, 'SAS': 2, 'EAS': 3, 'AMR': 4}

    # Order samples (rows) by most voted continent and population
    res_df['_continent_order'] = res_df['Most_voted_continent'].map(continent_rank)
    res_df['_pop_order'] = res_df['Most_voted_population'].map(pop_rank)
    res_df.sort_values(by=['_continent_order', '_pop_order'], inplace=True)
    
    # Two plots: one for population predictions and one for continent predictions
    fig_pop, ax_pop = plt.subplots(figsize=(12, 6))
    fig_continent, ax_continent = plt.subplots(figsize=(12, 6))
    
    model_cols_pop = [col for col in res_df.columns if col.startswith('model') and not col.endswith('_continent')]
    model_cols_continent = [col for col in res_df.columns if col.startswith('model') and col.endswith('_continent')]

    for i,(_,row) in enumerate(res_df.iterrows()):
        bottom = 0
        # Plot model predictions for population
        for j,col in enumerate(model_cols_pop):
            ax_pop.bar(i, height=1, bottom=bottom, color=pop_palette[row[col]],
                    width=1, linewidth=0)
            bottom += 1

        ax_pop.bar(i, height=1, bottom=bottom, color=pop_palette[row['Most_voted_population']],
                    width=1, linewidth=0)
        
        # Plot model predictions for continent
        bottom = 0
        for j,col in enumerate(model_cols_continent):
            ax_continent.bar(i, height=1, bottom=bottom, color=continent_palette[row[col]],
                    width=1, linewidth=0)
            bottom += 1
        ax_continent.bar(i, height=1, bottom=bottom, color=continent_palette[row['Most_voted_continent']],
                    width=1, linewidth=0)
    
    # Separate model predictions from most voted with horizontal line
    ax_pop.axhline(y=len(model_cols_pop), color="black", linewidth=1.2)
    ax_continent.axhline(y=len(model_cols_continent), color="black", linewidth=1.2)
    
    # Remove white space around and in the plot
    for ax in [ax_pop, ax_continent]:
        ax.set_xlim(-0.5, res_df.shape[0] - 0.5)
        ax.set_ylim(0, len(model_cols_pop)+1)
        ax.margins(x=0, y=0)

        # Set ytick labels to model names and "Most voted"
        ytick_positions = [0.5] + [i + 1.5 for i in range(len(model_cols_pop))]
        ytick_labels = [f"model{i}" for i in range(1, len(model_cols_pop)+1)] + ["Most voted"]

        ax.set_yticks(ytick_positions)
        ax.set_yticklabels(ytick_labels)

        # Set x-axis to samples
        ax.set_xlabel('Samples')
        ax.set_xticks([0, res_df.shape[0]])
        ax.set_xticklabels([0, res_df.shape[0]])

    # Legends
    handles = [
    Patch(facecolor=color, label=population)
    for population, color in pop_palette.items()
    ]

    ax_pop.legend(
        handles=handles,
        title="Population",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
    )
    
    handles = [
    Patch(facecolor=color, label=continent)
    for continent, color in continent_palette.items()
    ]

    ax_continent.legend(
        handles=handles,
        title="Continent",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
    )
    
    # Save plots
    fig_pop.savefig(outfile+"_barplot_population.png", bbox_inches="tight",pad_inches=0.15,dpi=300)
    fig_continent.savefig(outfile+"_barplot_continent.png", bbox_inches="tight",pad_inches=0.15,dpi=300)


def parse_args():
    parser = argparse.ArgumentParser(description='Group model predictions by sample and save to text file.')
    
    parser.add_argument(
        '--dietnet-results',
        type=str,
        required=True,
        help='Npz file of results for all models. Provide full path.'
    )

    parser.add_argument(
        '--sample-missingness',
        type=str,
        required=True,
        help='Files with missing rate by sample. Provide full path.'
    )

    parser.add_argument(
        '--folds',
        type=int,
        required=True,
        help='Number of folds.'
    )

    parser.add_argument(
        '--reps',
        type=int,
        required=True,
        help='Number of repetitions.'
    )

    parser.add_argument(
        '--pop-threshold',
        type=int,
        default=12,
        help='Minimum number of models for most voted prediction. Default: %(default)i'
    )

    parser.add_argument(
        '--continent-threshold',
        type=int,
        default=14,
        help='Minimum number of models for most voted prediction. Default: %(default)i'
    )

    parser.add_argument(
        '--out',
        type=str,
        required=True,
        help='Output name for model.'
    )
    
    return parser.parse_args()

if __name__ == '__main__':
    main()