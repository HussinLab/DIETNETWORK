#!/bin/bash
# Docker: optional PLINK_PREFIX=..., or basename as $1, or auto if exactly one trio in PLINK_DIR.

plink_path="/usr/local/bin/plink"
dietnet_code_path="/app"
dietnet_files_path="/data/dietnet_files"
models_files_path="/data/models"
plink_dir="${PLINK_DIR:-/data/plink}"

trio_prefix() {
  local p="${1%.bed}"; p="${p%.bim}"; p="${p%.fam}"
  [[ -f "$p.bed" && -f "$p.bim" && -f "$p.fam" ]] && echo "$p" || return 1
}

if p=$(trio_prefix "${PLINK_PREFIX:-}" 2>/dev/null); then
  plink_test=$p
elif [[ -n "${1:-}" ]] && p=$(trio_prefix "$plink_dir/$1"); then
  plink_test=$p
else
  shopt -s nullglob
  trios=()
  for b in "$plink_dir"/*.bed; do
    p=$(trio_prefix "${b%.bed}") && trios+=("$p")
  done
  shopt -u nullglob
  case ${#trios[@]} in
    0) echo "No PLINK trio in $plink_dir" >&2; exit 1 ;;
    1) plink_test=${trios[0]} ;;
    *)
      echo "Multiple trios — set PLINK_PREFIX or pass basename as \$1:" >&2
      printf '  %s\n' "$(printf '%s\n' "${trios[@]}" | LC_ALL=C sort -u)" >&2
      exit 1
      ;;
  esac
fi
output_name=$(basename "$plink_test")

#-----------------------------------------------------------------------------
# Pre-processing the plink files to get the same SNPs as used to train the DN
#-----------------------------------------------------------------------------
echo "---"
echo "Pre-processing plink files to match SNPs used to train the Dietnet"
echo "Using --bfile prefix: $plink_test"
echo ""

${plink_path} \
    --bfile "$plink_test" \
    --extract ${dietnet_files_path}/dietnet_snps.txt \
    --make-bed \
    --real-ref-alleles \
    --out ${output_name}_dietnetsnps_extracted

if [ ! -f ${output_name}_dietnetsnps_extracted.bim ]; then
    echo "Exiting program: No overlapping SNPs found between the plink query files and Diet Network SNPs."
    exit 1
fi

cut -f2 ${output_name}_dietnetsnps_extracted.bim > ${output_name}_dietnetsnps_extractedsnps.txt

comm -23 <(sort ${dietnet_files_path}/dietnet_snps.txt) <(sort ${output_name}_dietnetsnps_extractedsnps.txt) > ${output_name}_dietnetsnps_notextractedsnps.txt

cat ${output_name}_dietnetsnps_extracted.fam ${dietnet_files_path}/dummy.fam | cut -f1,2 > sample_order.txt
${plink_path} \
    --bfile ${output_name}_dietnetsnps_extracted \
    --bmerge ${dietnet_files_path}/dummy \
    --merge-mode 5 \
    --real-ref-alleles \
    --indiv-sort file sample_order.txt \
    --make-bed \
    --out ${output_name}_dietnetsnps_extracted_missingfilled

${plink_path} \
    --bfile ${output_name}_dietnetsnps_extracted_missingfilled \
    --remove ${dietnet_files_path}/dummy.sample \
    --recode A \
    --real-ref-alleles \
    --out ${output_name}_dietnetsnps_extracted_missingfilled

scale=$(echo "$(wc -l < ${dietnet_files_path}/dietnet_snps.txt) / $(wc -l < ${output_name}_dietnetsnps_extractedsnps.txt)" | bc -l)
echo "Scaling factor for missing SNPs: $scale"

rm ${output_name}_dietnetsnps_extracted.*
rm ${output_name}_dietnetsnps_extracted_missingfilled.b*
rm ${output_name}_dietnetsnps_extracted_missingfilled.fam
rm ${output_name}_dietnetsnps_extracted_missingfilled.nosex
rm ${output_name}_dietnetsnps_extracted_missingfilled.log
rm sample_order.txt

echo "---"
echo ""

echo "---"
echo "Creating HDF5 dataset for inference with Dietnet"

python ${dietnet_code_path}/inference_dataset.py \
--genotypes ${output_name}_dietnetsnps_extracted_missingfilled.raw \
--scale $scale \
--ncpus 1 \
--out ${output_name}.hdf5

rm ${output_name}_dietnetsnps_extracted_missingfilled.raw

echo "---"
echo ""

echo "---"
echo "Inference"

output_dir=${output_name}_DIETNET_RESULTS_BY_MODEL
if [ ! -d "$output_dir" ]; then
  mkdir $output_dir
fi

for fold in {1..5}; do
    for rep in {1..3}; do
        echo "Running inference with Diet Network model fold $fold, repeat $rep"
        python ${dietnet_code_path}/inference.py \
        --test-h5 ${output_name}.hdf5 \
        --model-param ${models_files_path}/weights_model${fold}_${rep}.pt \
        --snps-emb ${models_files_path}/snps_emb_model${fold}.npz \
        --norm-stats ${models_files_path}/norm_stats_model${fold}.npz \
        --out ${output_dir}/${output_name}_model${fold}_${rep}_infered.npz
        echo ""
    done
done

echo "---"
echo ""

python ${dietnet_code_path}/inference_combine_results.py \
--dietnet-results ${output_dir}/${output_name}_model{fold}_{rep}_infered.npz \
--out ${output_name}_dietnet_predictions.txt

python ${dietnet_code_path}/plot_results.py \
  --predictions ${output_name}_dietnet_predictions.txt \
  --out-dir ${output_name}_vote_plots \
  --selection uncertain

echo "Inference with Dietnet completed. Predictions saved in ${output_name}_dietnet_predictions.txt"
echo ""
echo "The SNP overlap with Diet Network is: $(wc -l < ${output_name}_dietnetsnps_extractedsnps.txt) out of $(wc -l < ${dietnet_files_path}/dietnet_snps.txt) SNPs used to train the Diet Network."
echo "Note that we suggest to not consider predictions if the SNP overlap is less than 1000 SNPs."