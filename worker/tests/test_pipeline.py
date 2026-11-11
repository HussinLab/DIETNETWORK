"""Unit tests for the pure-Python pre-flight checks in worker/worker/pipeline.py.

count_samples and check_allele_harmonization take no external dependencies
and run anywhere. check_snp_overlap shells out to plink against the
DN_SNPS panel baked into the worker image, so it's skipped unless both are
available (run this file inside a worker container -- see
tests/run_unit_tests.sh, which mounts dataTest/fixtures in and sets
FIXTURES_DIR).
"""
import os

import pytest

import conftest
from worker.config import settings
from worker.pipeline import check_allele_harmonization, check_snp_overlap, count_samples

PLINK_AVAILABLE = os.path.isfile(settings.plink_path)
PANEL_AVAILABLE = os.path.isdir(os.path.join(settings.dietnet_files_path, "DN_SNPS"))
FIXTURES_AVAILABLE = bool(conftest.FIXTURES_DIR) and os.path.isdir(conftest.FIXTURES_DIR)

requires_container = pytest.mark.skipif(
    not (PLINK_AVAILABLE and PANEL_AVAILABLE and FIXTURES_AVAILABLE),
    reason="needs plink + DN_SNPS panel (baked into the worker image) and dataTest/fixtures mounted in "
    "-- run via tests/run_unit_tests.sh, not bare pytest on the host",
)


# --- count_samples -- pure, no dependencies ---


def test_count_samples(tmp_path):
    fam = tmp_path / "x.fam"
    fam.write_text("fam1 ind1 0 0 1 -9\nfam1 ind2 0 0 2 -9\nfam2 ind3 0 0 1 -9\n")
    assert count_samples(str(tmp_path / "x")) == 3


def test_count_samples_empty(tmp_path):
    (tmp_path / "x.fam").write_text("")
    assert count_samples(str(tmp_path / "x")) == 0


# --- check_allele_harmonization -- pure, no dependencies ---


def _write_bim(path, rows):
    """rows: list of (snp_id, a1, a2)."""
    with open(path, "w") as f:
        for i, (snp_id, a1, a2) in enumerate(rows, start=1):
            f.write(f"1\t{snp_id}\t0\t{i}\t{a1}\t{a2}\n")


def test_check_allele_harmonization_classifies_each_case(tmp_path):
    # Reference (panel) alleles, one SNP per classification:
    reference = [
        ("matched", "A", "G"),  # non-palindromic
        ("swapped", "A", "G"),  # non-palindromic order swap
        ("flipped", "A", "G"),  # strand complement, same order
        ("ambiguous", "A", "T"),  # palindromic pair -- swap and flip look identical
        ("mismatched", "A", "G"),  # genuinely different alleles
        ("missing_code", "0", "G"),  # '0' -- excluded from comparison entirely
        ("only_in_reference", "C", "T"),  # not present in query at all
    ]
    query = [
        ("matched", "A", "G"),  # == reference
        ("swapped", "G", "A"),  # order reversed
        ("flipped", "T", "C"),  # complement of A/G, same order
        ("ambiguous", "T", "A"),  # order reversed on a palindromic pair
        ("mismatched", "C", "G"),  # neither swap nor flip of A/G
        ("missing_code", "0", "G"),
        ("only_in_query", "A", "C"),  # not present in reference -- ignored
    ]
    ref_path, query_path = tmp_path / "ref.bim", tmp_path / "query.bim"
    _write_bim(ref_path, reference)
    _write_bim(query_path, query)

    counts = check_allele_harmonization(str(query_path), str(ref_path))

    assert counts == {
        "compared": 5,  # excludes the two '0'-coded and the two SNPs only on one side
        "matched": 1,
        "swapped": 1,
        "flipped": 1,
        "ambiguous": 1,
        "mismatched": 1,
    }


def test_check_allele_harmonization_all_matched_below_threshold(tmp_path):
    rows = [(f"snp{i}", "A", "G") for i in range(20)]
    ref_path, query_path = tmp_path / "ref.bim", tmp_path / "query.bim"
    _write_bim(ref_path, rows)
    _write_bim(query_path, rows)

    counts = check_allele_harmonization(str(query_path), str(ref_path))
    mismatched = counts["swapped"] + counts["flipped"] + counts["ambiguous"]
    assert counts["compared"] == 20
    assert mismatched == 0


# --- check_snp_overlap -- shells out to plink; needs the real panel ---


@requires_container
def test_check_snp_overlap_low_overlap_fixture_below_threshold(tmp_path):
    overlap_count, overlap_total = check_snp_overlap(
        os.path.join(conftest.FIXTURES_DIR, "low_overlap"), str(tmp_path / "out")
    )
    assert overlap_total == 229986  # full DN_SNPS panel size
    assert overlap_count <= 400  # fixture only has 400 SNPs to begin with
    assert overlap_count < settings.min_reliable_snp_overlap


@requires_container
def test_check_snp_overlap_positive_control_above_threshold(tmp_path):
    positive_control = os.path.join(
        conftest.FIXTURES_DIR,
        "..",
        "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
    )
    overlap_count, overlap_total = check_snp_overlap(positive_control, str(tmp_path / "out"))
    assert overlap_count >= settings.min_reliable_snp_overlap
