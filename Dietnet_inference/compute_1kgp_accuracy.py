#!/bin/bash
#!/usr/bin/env python3

import argparse
import sys
import pandas as pd
import numpy as np

def main():
    args = parse_args()    
    
    dn_label_order = ['ACB', 'ASW', 'BEB', 'CDX', 'CEUGBR',
                      'CHB', 'CHS', 'CLM', 'ESN', 'FIN',
                      'GIH', 'GWD', 'IBS', 'JPT', 'KHV',
                      'LWK', 'MSL', 'MXL', 'PEL', 'PJL',
                      'PUR', 'STUITU', 'TSI', 'YRI']
    
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
    
    # Load true labels
    true_labels = pd.read_csv(args.true_labels, sep='\t')
    
    # Get accuracy for each model
    acc_by_model = []
    acc_by_model_continent = []
    for fold in range(1, args.folds + 1):
        for rep in range(1, args.reps + 1):
            # Load results
            model_output = args.model_output + '_model{fold}_{rep}_infered.npz'.format(fold=fold,rep=rep)
            model_res = np.load(model_output, allow_pickle=True)
            
            # Put results in df
            res_df = pd.DataFrame({'sample':[i for i in model_res['samples']],
                                   'pred':[dn_label_order[int(i)] for i in model_res['preds']],
                                   'pred_continent':[pop_to_continent[dn_label_order[int(i)]] for i in model_res['preds']]})

            # Add pop and continental labels
            res_and_labels = pd.merge(true_labels, res_df, on='sample', how='inner')
            res_and_labels['continent'] = res_and_labels['label'].map(pop_to_continent)
            
            # Compute accuracy (population-level)
            n_correct = (res_and_labels['pred']==res_and_labels['label']).sum()
            acc_by_model.append(n_correct/res_and_labels.shape[0])
            
            # Compute accuracy (continent-level)
            n_correct_continent = (res_and_labels['pred_continent']==res_and_labels['continent']).sum()
            acc_by_model_continent.append(n_correct_continent/res_and_labels.shape[0])

    print('Population-level accuracy by model:')
    print(acc_by_model)
    print('Continent-level accuracy by model:')
    print(acc_by_model_continent)
    
    pop_mean_acc = np.mean(acc_by_model)
    continent_mean_acc = np.mean(acc_by_model_continent)
    print('Average population-level accuracy across all models: {}'.format(pop_mean_acc))
    print('Average continent-level accuracy across all models: {}'.format(continent_mean_acc))
    
    if continent_mean_acc < 0.95:
        print(f"Stopping pipeline: Mean continent-level accuracy is below 95% ({continent_mean_acc:.2%})")
        sys.exit(1)
    
    # If the script reaches this point, it means the accuracy is above 95%
    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute prediction accuracy for each model."
    )
    
    parser.add_argument("--model-output",
                        required=True,
                        help="Path to model outputs.")
    
    parser.add_argument(
        "--folds",
        required=True,
        type=int,
        help="Number of folds (numbered from 1)."
    )
    
    parser.add_argument(
        "--reps",
        required=True,
        type=int,
        help="Number of repetitions or seeds (numbered from 1).",
    )
    
    parser.add_argument(
        "--true-labels",
        required=True,
        type=str,
        help="Tab-separated file of true labels with sample and label columns",
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()