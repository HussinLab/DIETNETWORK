#!/bin/bash

# Description:
# This script prepares a user-provided PLINK genotype dataset for inference with
# Diet Network models. It identifies the overlap between the user's SNPs and the
# SNPs used to train Diet Network. Performance of the SNP set is checked by running
# inference on 1KGP samples with the SNP set and verifying that model accuracy meets
# the required threshold. If the check passes, the script runs inference on the user
# dataset.

# Output
# This script returns compiled population and continent predictions across models,
# and PCA representation of the models' last hidden-layer outputs.

# Usage : 
# bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> \
#               <plink_user_files_prefix> <output_name> <nb_folds> <nb_reps>

# Command-line arguments to variables
plink_path="$1"
dietnet_code_path="$2"
dietnet_files_path="$3"
plink_user_files="$4"
output_name="$5"
nb_folds="$6"
nb_reps="$7"


# Get overlap between user uploaded SNPs and Diet Network SNPs 
#--------------------------------------------------------------
echo "---"
echo "Pre-processing plink files to match SNPs used to train the Dietnet"
echo ""

# Rewrite the user SNP ids (in bim) to the Diet Network convention:
# chr:pos:refAllele:altAllele
cp ${plink_user_files}.bim ${plink_user_files}_temp.bim

awk 'BEGIN { OFS="\t" }
{
    # Does the chromosome name start with "chr"? If not, add it.
    chr_col = $1
    if (chr_col !~ /^chr/) {
        chr_col = "chr" chr_col
    }

    $2 = chr_col ":" $4 ":" $6 ":" $5
    print
}' ${plink_user_files}.bim > ${plink_user_files}_temp.bim

mv ${plink_user_files}.bim ${plink_user_files}_original.bim
mv ${plink_user_files}_temp.bim ${plink_user_files}.bim

# Extract dietnet snps from the plink user file
${plink_path} \
    --bfile ${plink_user_files} \
    --extract ${dietnet_files_path}/DN_SNPS/dietnet_snps.txt \
    --make-bed \
    --real-ref-alleles \
    --out ${output_name}

# Check if the .bim file was created (no overlap if the bim file does not exist)
if [ ! -f ${output_name}.bim ]; then
    echo "Exiting program: No overlapping SNPs found between the plink query files and Diet Network SNPs."
    exit 1
fi

# Dietnet snps found in test set
cut -f2 ${output_name}.bim > ${output_name}_included_snps.txt

# Dietnet snps not found in test set
comm -23 <(sort ${dietnet_files_path}/DN_SNPS/dietnet_snps.txt) <(sort ${output_name}_included_snps.txt) > ${output_name}_excluded_snps.txt


# Inference on 1KGP using user-Dietnet overlaping SNPs
#------------------------------------------------------
echo "---"
echo "Quality control of SNP set on 1KGP dataset"

output_dir="1KGP_RESULTS"
if [ ! -d "$output_dir" ]; then
  mkdir $output_dir
fi

# Create 1KGP inference hdf5 by setting SNPs not found in 
# user dataset to -1 in the original Diet Network 1KGP hdf5
python ${dietnet_code_path}/create_1kgp_hdf5.py \
--kgp-dataset ${dietnet_files_path}/1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5 \
--overlap-snps ${output_name}_included_snps.txt \
--out ${output_dir}/${output_name}_1kgp_overlapSNPs.hdf5

# Run inference on 1KGP
for fold in $(seq 1 "$nb_folds"); do
    for rep in $(seq 1 "$nb_reps"); do
        echo "Infering with model fold $fold, repeat $rep"
        python ${dietnet_code_path}/inference.py \
        --test-h5 ${output_dir}/${output_name}_1kgp_overlapSNPs.hdf5 \
        --partition ${dietnet_files_path}/1KGP/1KGP_2322inds_24pops_230Ksnps_parition.npz \
        --model-param ${dietnet_files_path}/DN_MODELS/weights_model${fold}_${rep}.pt \
        --snps-emb ${dietnet_files_path}/DN_MODELS/snps_emb_model${fold}.npz \
        --norm-stats ${dietnet_files_path}/DN_MODELS/norm_stats_model${fold}.npz \
        --fold $((fold - 1)) \
        --out ${output_dir}/${output_name}_model${fold}_${rep}_infered.npz
        echo ""
    done
done

# Compute accuracy on 1KGP and exit if accuracy is below threshold (95%)
if ! python ${dietnet_code_path}/compute_1kgp_accuracy.py \
    --model-output ${output_dir}/${output_name} \
    --folds ${nb_folds} \
    --reps ${nb_reps} \
    --true-labels ${dietnet_files_path}/1KGP/1000G.2322samples.labels.txt; then
    echo "Exit."
    rm ${output_name}.*
    exit 1
fi

echo "---"
echo ""


# Preprocess user dataset
#-------------------------
# Fill extracted plink with SNPs (set as missing) to match SNPs used to train the DN
# (This is done by merging the extracted plink file with a dummy plink file
# of one 1KGP sample with SNPs used to train the dietnet, 
# using merge-mode 5  which fills in missing SNPs)
cat ${output_name}.fam ${dietnet_files_path}/DN_SNPS/dummy.fam | cut -f1,2 > sample_order.txt
${plink_path} \
    --bfile ${output_name} \
    --bmerge ${dietnet_files_path}/DN_SNPS/dummy \
    --merge-mode 5 \
    --real-ref-alleles \
    --indiv-sort file sample_order.txt \
    --make-bed \
    --out ${output_name}_missingfilled

# Compute missingness per sample (how many genotypes are missing in the dietnet snps extracted plink file)
${plink_path} --bfile ${output_name}_missingfilled --missing --out ${output_name}_missingnesspersample

# Additive encoding (and remove dummy sample)
${plink_path} \
    --bfile ${output_name}_missingfilled \
    --remove ${dietnet_files_path}/DN_SNPS/dummy.sample \
    --recode A \
    --real-ref-alleles \
    --out ${output_name}_missingfilled

# Scaling for missing SNPs
scale=$(echo "$(wc -l < ${dietnet_files_path}/DN_SNPS/dietnet_snps.txt) / $(wc -l < ${output_name}_included_snps.txt)" | bc -l)
echo "Scaling factor for missing SNPs: $scale"

echo "---"
echo ""


# Create hdf5 dataset for inference with Dietnet
#------------------------------------------------
echo "---"
echo "Creating HDF5 dataset for inference with Dietnet"

python ${dietnet_code_path}/create_user_hdf5.py \
--genotypes ${output_name}_missingfilled.raw \
--scale $scale \
--ncpus 1 \
--out ${output_name}.hdf5

echo "---"
echo ""


# Inference with Dietnet
#------------------------
echo "---"
echo "Inference on user-provided dataset"

output_dir=${output_name}_RESULTS
if [ ! -d "$output_dir" ]; then
  mkdir $output_dir
fi

for fold in $(seq 1 "$nb_folds"); do
    for rep in $(seq 1 "$nb_reps"); do
        echo "Running inference with Diet Network model fold $fold, repeat $rep"
        python ${dietnet_code_path}/inference.py \
        --test-h5 ${output_name}.hdf5 \
        --model-param ${dietnet_files_path}/DN_MODELS/weights_model${fold}_${rep}.pt \
        --snps-emb ${dietnet_files_path}/DN_MODELS/snps_emb_model${fold}.npz \
        --norm-stats ${dietnet_files_path}/DN_MODELS/norm_stats_model${fold}.npz \
        --out ${output_dir}/${output_name}_model${fold}_${rep}_infered.npz
        echo ""
    done
done

echo "---"
echo ""

# Create output file with all model predictions for each sample
python ${dietnet_code_path}/compile_user_results.py \
--dietnet-results ${output_dir}/${output_name}_model{fold}_{rep}_infered.npz \
--sample-missingness ${output_name}_missingnesspersample.imiss \
--folds $nb_folds \
--reps $nb_reps \
--pop-threshold 12 \
--continent-threshold 14 \
--out ${output_name}

# Last hidden layer PCA representation
#--------------------------------------
# Inference 1KGP
output_dir=1KGP_RESULTS

for fold in $(seq 1 "$nb_folds"); do
    for rep in $(seq 1 "$nb_reps"); do
        echo "Running inference on 1KGP with Diet Network model fold $fold, repeat $rep"
        python ${dietnet_code_path}/inference.py \
        --test-h5 ${output_dir}/${output_name}_1kgp_overlapSNPs.hdf5 \
        --model-param ${dietnet_files_path}/DN_MODELS/weights_model${fold}_${rep}.pt \
        --snps-emb ${dietnet_files_path}/DN_MODELS/snps_emb_model${fold}.npz \
        --norm-stats ${dietnet_files_path}/DN_MODELS/norm_stats_model${fold}.npz \
        --out ${output_dir}/${output_name}_model${fold}_${rep}_infered_allsamples.npz
        echo ""
    done
done

# Compute PCA and output representation
echo "Computing PCA on models last hidden layer for representation"
python ${dietnet_code_path}/hidden_layer_pca.py \
--kgp-hdf5 ${output_dir}/${output_name}_1kgp_overlapSNPs.hdf5 \
--kgp-model-output ${output_dir}/${output_name}_model{fold}_{rep}_infered_allsamples.npz \
--user-hdf5 ${output_name}.hdf5 \
--user-model-output ${output_name}_RESULTS/${output_name}_model{fold}_{rep}_infered.npz \
--user-compiled-predictions ${output_name}_predictions.txt \
--folds ${nb_folds} \
--reps ${nb_reps} \
--output ${output_name}


# Remove intermediary files
rm ${output_name}.b*
rm ${output_name}.fam
rm ${output_name}.nosex
rm ${output_name}.log
rm ${output_name}_missingfilled.*
rm sample_order.txt
rm ${output_name}_missingnesspersample.*
rm ${output_name}.hdf5
rm -r 1KGP_RESULTS
rm -r ${output_name}_RESULTS

echo "Inference with Dietnet completed."
echo "The SNP overlap with Diet Network is: $(wc -l < ${output_name}_included_snps.txt) out of $(wc -l < ${dietnet_files_path}/DN_SNPS/dietnet_snps.txt) SNPs used to train the Diet Network."