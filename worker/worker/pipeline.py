"""
The actual glue: user upload (VCF/bgen) -> PLINK 1.9 binary -> infer.sh ->
structured predictions. Every subprocess call is logged; nothing here talks
to the network at request time (models/SNP files are baked into the image
at build time -- see ops/scripts/fetch_zenodo_models.sh).
"""
import logging
import os
import subprocess

import pandas as pd

from worker.config import settings

logger = logging.getLogger("worker.pipeline")


class PipelineError(Exception):
    """Raised for any pipeline failure; message is safe to show to end users."""


def _run(cmd: list[str], cwd: str | None = None) -> None:
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("Command failed (%s): stdout=%s stderr=%s", cmd[0], proc.stdout[-4000:], proc.stderr[-4000:])
        raise PipelineError(f"Step '{os.path.basename(cmd[0])}' failed. See worker logs for job diagnostics.")
    logger.info(proc.stdout[-2000:])
    # infer.sh (Dietnet_inference/infer.sh, vendored model code) doesn't check
    # the exit code of any of the python steps it shells out to, so it can
    # exit 0 -- "succeeding" -- even when e.g. inference_dataset.py crashed
    # and no predictions were produced. Always surface stderr, not just on a
    # nonzero return code, or the real traceback never reaches the logs.
    if proc.stderr.strip():
        logger.warning("%s produced stderr despite exit 0: %s", cmd[0], proc.stderr[-4000:])


def convert_vcf_to_plink(vcf_path: str, out_prefix: str) -> str:
    """PLINK 1.9: VCF (or VCF.GZ) -> .bed/.bim/.fam, with a missingness QC
    filter applied in the same pass (--geno drops SNPs missing in >10% of
    samples). Genotypes are expected to already be harmonized to GRCh38;
    the platform cannot re-map genome builds (see UI/README warning).

    --real-ref-alleles: without it, plink1.9's --make-bed default is to
    reassign A2 to whichever allele is major *in this sample*, silently
    discarding the VCF's own REF/ALT convention for any SNP where that
    differs from the reference panel's. check_allele_harmonization (run
    later, against this same converted file) would then see a spurious
    swap for every such SNP -- rejecting well-harmonized uploads as an
    artifact of this conversion step, not a real problem with the data."""
    _run(
        [
            settings.plink_path,
            "--vcf",
            vcf_path,
            "--real-ref-alleles",
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("VCF could not be converted to PLINK format. Check that the file is a valid VCF.")
    return out_prefix


def convert_bgen_to_plink(bgen_path: str, sample_path: str, out_prefix: str) -> str:
    """PLINK2: bgen (+ .sample) -> .bed/.bim/.fam, QC filter in the same pass."""
    _run(
        [
            settings.plink2_path,
            "--bgen",
            bgen_path,
            "ref-first",
            "--sample",
            sample_path,
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("bgen could not be converted to PLINK format. Check the .bgen/.sample pair.")
    return out_prefix


def requalify_plink(in_prefix: str, out_prefix: str) -> str:
    """PLINK 1.9: already-PLINK .bed/.bim/.fam upload -> re-written .bed/.bim/.fam
    at a known location, with the same missingness QC filter applied as the
    VCF/bgen paths (--geno) so all three input types get identical
    filtering before infer.sh, rather than trusting the upload as-is.

    --real-ref-alleles: see convert_vcf_to_plink -- same plink1.9 default
    (reassign A2 to the sample's major allele) applies to --bfile input
    too, so without this flag a well-harmonized upload can come out of
    this *lossless* requalification pass with ~a quarter of its SNPs
    silently A1/A2-swapped relative to what the user actually uploaded."""
    _run(
        [
            settings.plink_path,
            "--bfile",
            in_prefix,
            "--real-ref-alleles",
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("Uploaded PLINK files could not be processed. Check that the .bed/.bim/.fam set is valid.")
    return out_prefix


def count_samples(plink_prefix: str) -> int:
    """Number of samples in a converted PLINK set (one line per sample in
    .fam). Checked right after conversion -- VCF/bgen sample counts aren't
    known before that point -- so an oversized upload is rejected before any
    PLINK/inference work is spent on it."""
    with open(plink_prefix + ".fam") as f:
        return sum(1 for _ in f)


def check_snp_overlap(plink_prefix: str, tmp_out_prefix: str) -> tuple[int, int]:
    """Fast pre-flight overlap check: runs the same '--extract dietnet_snps.txt'
    step infer.sh performs as its first stage, but *before* committing to the
    full 15-model ensemble. Lets a doomed-to-be-unreliable job (< 1000
    overlapping SNPs) be rejected immediately instead of after several
    minutes of inference. infer.sh redoes this extraction itself, so this is
    a small amount of duplicated (cheap) work in exchange for never running
    the ensemble on data we already know is unreliable."""
    panel_file = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dietnet_snps.txt")
    with open(panel_file) as f:
        overlap_total = sum(1 for _ in f)

    _run(
        [
            settings.plink_path,
            "--bfile",
            plink_prefix,
            "--extract",
            panel_file,
            "--make-bed",
            "--real-ref-alleles",
            "--out",
            tmp_out_prefix,
        ]
    )
    # Mirrors infer.sh's own check: PLINK can complete without producing a
    # .bim when there's no overlap at all, rather than exiting non-zero.
    if not os.path.isfile(tmp_out_prefix + ".bim"):
        return 0, overlap_total
    with open(tmp_out_prefix + ".bim") as f:
        overlap_count = sum(1 for _ in f)
    return overlap_count, overlap_total


_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


def _complement(allele: str) -> str | None:
    """None for indels/multi-base alleles or missing ('0') codes -- strand
    complementing only makes sense for a single standard base."""
    return _COMPLEMENT.get(allele)


def _read_bim_alleles(bim_path: str) -> dict[str, tuple[str, str]]:
    alleles: dict[str, tuple[str, str]] = {}
    with open(bim_path) as f:
        for line in f:
            fields = line.split()
            if len(fields) < 6:
                continue
            snp_id, a1, a2 = fields[1], fields[4].upper(), fields[5].upper()
            alleles[snp_id] = (a1, a2)
    return alleles


def check_allele_harmonization(extracted_bim_path: str, dummy_bim_path: str) -> dict[str, int]:
    """Compares each overlapping SNP's alleles against the training panel's
    reference alleles (DN_SNPS/dummy.bim -- the one 1KGP sample infer.sh
    merges against, carrying the panel's canonical A1/A2). infer.sh runs
    PLINK with --real-ref-alleles, which tells it to trust the query's A1/A2
    as given rather than auto-flip by allele frequency -- so a systematically
    swapped or strand-flipped upload would otherwise silently invert the
    additive dosage for those SNPs instead of erroring.

    Returns counts by classification. 'ambiguous' covers A/T and C/G SNPs,
    where a strand flip and an allele-order swap produce the identical
    observed pair -- the two causes genuinely can't be told apart there."""
    query = _read_bim_alleles(extracted_bim_path)
    reference = _read_bim_alleles(dummy_bim_path)

    counts = {"compared": 0, "matched": 0, "swapped": 0, "flipped": 0, "ambiguous": 0, "mismatched": 0}
    for snp_id, (q1, q2) in query.items():
        ref = reference.get(snp_id)
        if ref is None:
            continue
        r1, r2 = ref
        if "0" in (q1, q2, r1, r2):
            continue  # missing/monomorphic allele code -- not a meaningful comparison

        counts["compared"] += 1
        if (q1, q2) == (r1, r2):
            counts["matched"] += 1
            continue

        c1, c2 = _complement(r1), _complement(r2)
        palindromic = c1 == r2 and c2 == r1  # A/T or C/G pair

        if (q1, q2) == (r2, r1):
            counts["ambiguous" if palindromic else "swapped"] += 1
        elif c1 is not None and (q1, q2) in ((c1, c2), (c2, c1)):
            counts["flipped"] += 1
        else:
            counts["mismatched"] += 1
    return counts


def run_infer(plink_prefix: str, output_prefix: str) -> str:
    """Runs Dietnet_inference/infer.sh with the REAL argument order (the
    README's order is wrong -- verified against the script itself):

        bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>

    <output_name> must be a bare relative prefix (not an absolute path):
    infer.sh does `output_dir=${output_name}_DIETNET_RESULTS_BY_MODEL` and
    then writes per-fold results to `${output_dir}/${output_name}_model...`,
    i.e. it concatenates output_name into itself a second time. Passing an
    absolute output_name there produces a broken doubled-absolute path (e.g.
    "/a/b_DIETNET_RESULTS_BY_MODEL//a/b_model5_1_infered.npz"), so every
    fold/rep silently fails to save its .npz and the final combine step has
    nothing to read -- infer.sh doesn't check those exit codes, so it still
    prints "completed" and exits 0. We run with cwd set to output_prefix's
    directory (below) so a relative name still lands in the right place.
    """
    infer_script = os.path.join(settings.dietnet_code_path, "infer.sh")
    output_dir = os.path.dirname(output_prefix)
    output_name = os.path.basename(output_prefix)
    os.makedirs(output_dir, exist_ok=True)
    _run(
        [
            "bash",
            infer_script,
            settings.plink_path,
            settings.dietnet_code_path,
            settings.dietnet_files_path,
            plink_prefix,
            output_name,
        ],
        cwd=output_dir,
    )
    predictions_file = f"{output_prefix}_dietnet_predictions.txt"
    if not os.path.isfile(predictions_file):
        raise PipelineError("Inference completed without producing a predictions file.")
    return predictions_file


def parse_predictions(predictions_file: str) -> list[dict]:
    """Parses <output_prefix>_dietnet_predictions.txt (tab-delimited: sample,
    model1..model15 population calls, all_models summary) into JSON-able rows."""
    df = pd.read_csv(predictions_file, sep="\t")
    return df.to_dict(orient="records")
