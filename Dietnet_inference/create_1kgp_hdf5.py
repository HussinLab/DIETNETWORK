import argparse
import h5py
import numpy as np

def main():
    args = parse_arguments()

    with h5py.File(args.kgp_dataset, 'r') as kgp_file:
        # Load SNPs in dietnet-user overlap
        with open(args.overlap_snps, 'r') as f:
            overlap_snps = [line.strip() for line in f]
            
        overlap_snps_formatted = [snp + '_' + snp.split(":")[-1] for snp in overlap_snps]  # Format SNPs to match 1KGP SNP names
        
        with h5py.File(args.kgp_dataset, 'r') as kgp_file:
            # Load the SNPs from the 1KGP dataset
            kgp_snps = [i.decode() for i in kgp_file['snp_names'][:]]

            kgp_genotypes = kgp_file['inputs'][:]

        
            # Find the indices of the SNPs not in the overlap list
            missingSNPs_indices = np.where(~np.isin(kgp_snps, overlap_snps_formatted))[0]
            
            # Set to -1 genotypes at missingSNPs indices
            kgp_genotypes[:, missingSNPs_indices] = -1
            
            # Create a new HDF5 file for the inference dataset
            with h5py.File(args.output_name, 'w') as output_file:
                # Create a dataset for the overlapping SNPs
                output_file.create_dataset('inputs', data=kgp_genotypes)
                scale = len(kgp_snps) / len(overlap_snps_formatted)
                output_file.create_dataset('scale', data=np.array([scale]))
                
                # Copy other datasets from the original 1KGP hdf5
                for key in kgp_file.keys():
                    if key != 'inputs':
                        output_file.create_dataset(key, data=kgp_file[key][:])


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Create a new hdf5 dataset for inference with SNPs overlapping SNPs in user dataset"
        )
    
    parser.add_argument("--kgp-dataset",
                        type=str,
                        required=True,
                        help="Path to the 1KGP hdf5 dataset"
                        )
    
    parser.add_argument("--overlap-snps",
                        type=str,
                        required=True,
                        help="File containing the overlapping SNPs between user dataset and Diet Network SNPs"
                        )
    
    parser.add_argument("--output_name",
                        type=str,
                        required=True,
                        help="Output name prefix for results"
                        )
    
    return parser.parse_args()

if __name__ == "__main__":
    main()