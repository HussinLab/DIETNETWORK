"""
Script to parse and save data into a hdf5 file format
"""
import argparse
import os
import multiprocessing as mp
import time

import numpy as np

import h5py


def main():
    args = parse_args()
    start_time = time.time()

    #----------------------------------------------
    #               PARSE GENOTYPES
    #----------------------------------------------
    genotype_start_time = time.time()

    # Multiprocessing to load lines in parallel
    ncpus = args.ncpus
    print('Parsing genotypes using {} cpu(s)'.format(ncpus))
    pool = mp.Pool(processes=ncpus) #this starts ncpus nb of processes

    # Results returned by processes
    results = []

    # Every line is read by a different process
    with open(args.genotypes, 'r') as f:
        header_line = next(f)
        for line in f:
            # Add sample, sample's genotype accros all SNPs
            results.append(pool.apply_async(parse_genotypes, args=(line,)))

    # Get parsed samples and genotypes
    results_values = [p.get() for p in results]
    samples = np.array([i[0] for i in results_values])
    genotypes = np.array([i[1] for i in results_values])

    # Get snps names from header line
    snps = np.array([i.strip() for i in header_line.split(' ')[6:]], dtype='S')

    print('Parsed {} genotypes of {} samples in {} seconds'.format(
          len(snps), len(samples), time.time() - genotype_start_time))

    #----------------------------------------------
    #           WRITE DATASET TO FILE
    #----------------------------------------------
    print('Saving dataset to {}'.format(args.out))

    # Create dataset
    f = h5py.File(args.out, 'w')

    # Input features
    f.create_dataset('inputs', data=genotypes)
    # SNP names (Hdf5 doesn't support np UTF-8 encoding: snps.astype('S'))
    f.create_dataset('snp_names', data=snps.astype('S'))
    # Samples
    f.create_dataset('samples', data=samples.astype('S'))
    # Scale
    f.create_dataset('scale', data=np.array([args.scale]))

    f.close()

    print('Created hdf5 dataset in {} seconds'.format(time.time()-start_time))


# Load genotypes of a sample from a line in the genotype file
def parse_genotypes(line):
    # Line contains FID, IID, PAT, MAT, SEX, PHENOTYPE, and then genotypes of all SNPs (space-delimited)
    sample = (line.split(' ')[1]).strip()

    # Fill with genotypes of all SNPs for the individual
    genotypes = []
    for i in line.split(' ')[6:]:
        # Replace missing values with -1
        if i.strip() == './.' or i.strip() == 'NA':
            genotype = -1
        else:
            genotype = int(i.strip())

        genotypes.append(genotype)

    genotypes = np.array(genotypes, dtype='int8')

    return sample, genotypes


def parse_args():
    parser = argparse.ArgumentParser(
            description='Create hdf5 dataset from genotype and label files.'
            )

    # Genotype file
    parser.add_argument(
            '--genotypes',
            type=str,
            required=True,
            help=('File of samples and their genotypes '
                  '(tab-separated format, one sample per line). '
                  'Missing genotypes can be encoded with NA, .\. or -1. '
                  'Provide full path')
            )
    
    # Scale for non-missing genotypes
    parser.add_argument(
            '--scale',
            type=float,
            required=True,
            help='Factor for scaling non-missing genotypes.'
            )

    # Number of cpus for parallel loading of genotype file
    parser.add_argument(
            '--ncpus',
            type=int,
            default=1,
            help=('Number of cpus available to parse genotypes in parallel. '
                  'Default: %(default)i')
            )
    
    parser.add_argument(
            '--out',
            required=True,
            type=str,
            help=('Output filename')
            )

    return parser.parse_args()


if __name__ == '__main__':
    main()