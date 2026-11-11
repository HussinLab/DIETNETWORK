#!/usr/bin/env python3
"""Generates the pre-flight rejection fixtures from TESTING.md section 2
(2a low SNP overlap, 2b swapped alleles) from the real dataTest 1000G trio.

Pure Python, no plink/Docker dependency: PLINK1 .bed is SNP-major (3-byte
magic header 0x6c 0x1b 0x01, then ceil(n_samples/4) bytes per SNP, in the
same order as .bim rows) -- so subsetting SNPs is just copying byte blocks,
not genotype-aware work.

2c (sample count > max_samples) and 2d (upload size > max_upload_mb) don't
need generated files -- tests/run_all.sh exercises them by temporarily
lowering MAX_SAMPLES / MAX_UPLOAD_MB against this same unmodified trio,
per TESTING.md's own recommendation ("simpler... exercises the same code
path").
"""
from __future__ import annotations

import math
import os
import random

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(
    REPO_ROOT,
    "dataTest",
    "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
)
OUT_DIR = os.path.join(REPO_ROOT, "dataTest", "fixtures")
LOW_OVERLAP_SNP_COUNT = 400  # well under min_reliable_snp_overlap (1000)
BED_MAGIC = b"\x6c\x1b\x01"


def bytes_per_snp(n_samples: int) -> int:
    return math.ceil(n_samples / 4)


def write_snp_subset(bim_lines: list[str], indices: list[int], n_samples: int, out_prefix: str) -> None:
    bps = bytes_per_snp(n_samples)
    with open(SRC + ".bed", "rb") as f:
        header = f.read(3)
        if header != BED_MAGIC:
            raise SystemExit(f"Unexpected .bed header {header!r} -- not SNP-major PLINK1 format")
        blocks = []
        for i in indices:
            f.seek(3 + i * bps)
            blocks.append(f.read(bps))
    with open(out_prefix + ".bed", "wb") as f:
        f.write(header)
        f.writelines(blocks)
    with open(out_prefix + ".bim", "w") as f:
        f.writelines(bim_lines[i] for i in indices)


def symlink_unchanged(src_ext: str, out_prefix: str, dst_ext: str | None = None) -> None:
    """Relative symlink (not absolute) so dataTest/ stays self-contained when
    bind-mounted into a container at a different path (see
    tests/run_unit_tests.sh)."""
    dst = out_prefix + (dst_ext or src_ext)
    if os.path.islink(dst) or os.path.exists(dst):
        os.remove(dst)
    os.symlink(os.path.relpath(SRC + src_ext, os.path.dirname(dst)), dst)


def main() -> None:
    if not os.path.isfile(SRC + ".bim"):
        raise SystemExit(f"Source fixture not found: {SRC}.bed/.bim/.fam -- is dataTest/ present?")

    os.makedirs(OUT_DIR, exist_ok=True)

    with open(SRC + ".bim") as f:
        bim_lines = f.readlines()
    with open(SRC + ".fam") as f:
        n_samples = sum(1 for _ in f)
    print(f"Source: {len(bim_lines)} SNPs, {n_samples} samples")

    # -- 2a: SNP overlap < min_reliable_snp_overlap (1000) --
    random.seed(1234)  # reproducible fixture across runs
    low_prefix = os.path.join(OUT_DIR, "low_overlap")
    low_indices = sorted(random.sample(range(len(bim_lines)), LOW_OVERLAP_SNP_COUNT))
    write_snp_subset(bim_lines, low_indices, n_samples, low_prefix)
    symlink_unchanged(".fam", low_prefix)
    print(f"low_overlap.{{bed,bim,fam}}: {LOW_OVERLAP_SNP_COUNT} SNPs (>= worker's overlap count vs the "
          f"DietNet panel, since dataTest's own SNP set IS the panel -- comfortably under the 1000 floor)")

    # -- 2b: A1/A2 swapped vs the reference panel (dataTest.bim already IS the
    # panel's SNP set/allele coding, so swapping every row's A1/A2 columns
    # guarantees ~100% of overlapping SNPs fail harmonization) --
    swapped_prefix = os.path.join(OUT_DIR, "swapped")
    with open(swapped_prefix + ".bim", "w") as out:
        for line in bim_lines:
            fields = line.rstrip("\n").split()
            fields[4], fields[5] = fields[5], fields[4]
            out.write("\t".join(fields) + "\n")
    symlink_unchanged(".bed", swapped_prefix)
    symlink_unchanged(".fam", swapped_prefix)
    print("swapped.{bed,bim,fam}: full SNP set, A1/A2 columns swapped")

    print()
    print("2c/2d: no fixture needed -- see tests/run_all.sh (temporarily lowers")
    print("MAX_SAMPLES / MAX_UPLOAD_MB and re-uploads the unmodified dataTest trio).")


if __name__ == "__main__":
    main()
