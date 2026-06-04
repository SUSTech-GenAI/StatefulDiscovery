---
name: pysam
description: "NGS data processing: read/write SAM/BAM/CRAM alignments, VCF/BCF variants, FASTA/FASTQ. Calculate coverage, perform pileup, run samtools/bcftools commands. Invoke when query involves sequencing alignment, variant calling, coverage depth, or read mapping."
---

# Pysam

Python interface to htslib, samtools, and bcftools for genomic data processing.

## When to Use

- Working with sequencing alignment files (BAM/SAM/CRAM)
- Calculating coverage or read depth
- Variant calling and analysis (VCF/BCF)
- Processing FASTQ reads
- Running samtools/bcftools commands from Python

## Installation

```bash
pip install pysam
```

This also provides `samtools` and `bcftools` command-line access via Python.

## BWA-MEM Mapping Pipeline

BWA must be installed separately: `conda install -c bioconda bwa` or `apt install bwa`.

```bash
# Index reference
bwa index reference.fna

# Map paired-end reads
bwa mem -t 4 -R '@RG\tID:sample1\tSM:sample1\tPL:ILLUMINA\tLB:lib1\tPU:unit1' \
  reference.fna reads_1.fastq reads_2.fastq | \
  samtools sort -o aligned.bam

# Index BAM
samtools index aligned.bam
```

Or via pysam:
```python
import pysam

# Sort and index
pysam.sort("-o", "sorted.bam", "input.bam")
pysam.index("sorted.bam")
```

## Coverage Calculation

```python
import pysam
import numpy as np

# Method 1: samtools depth
pysam.depth("-a", "-o", "depth.txt", "aligned.bam")

# Method 2: Python pileup
bam = pysam.AlignmentFile("aligned.bam", "rb")
total_depth = 0
total_bases = 0
for pileup_col in bam.pileup():
    total_depth += pileup_col.n
    total_bases += 1
avg_coverage = total_depth / total_bases if total_bases > 0 else 0

# Method 3: Using count_coverage for a region
# Returns 4 arrays (A, C, G, T counts per position)
a, c, g, t = bam.count_coverage("chr1", 0, 1000)
depth_per_pos = np.array(a) + np.array(c) + np.array(g) + np.array(t)
```

## Variant Calling (bcftools)

```bash
# Call variants
bcftools mpileup -f reference.fna aligned.bam | bcftools call -mv -Oz -o variants.vcf.gz
bcftools index variants.vcf.gz

# Stats (includes Ts/Tv ratio)
bcftools stats variants.vcf.gz > stats.txt
```

Via pysam:
```python
import pysam

# Read VCF
vcf = pysam.VariantFile("variants.vcf.gz")
for rec in vcf:
    print(f"{rec.chrom}:{rec.pos} {rec.ref}>{rec.alts} QUAL={rec.qual}")
```

## Ts/Tv Ratio Calculation

```python
transitions = {'AG', 'GA', 'CT', 'TC'}
ts_count = 0
tv_count = 0

vcf = pysam.VariantFile("variants.vcf.gz")
for rec in vcf:
    if rec.alts and len(rec.ref) == 1 and len(rec.alts[0]) == 1:  # SNPs only
        change = rec.ref + rec.alts[0]
        if change in transitions:
            ts_count += 1
        else:
            tv_count += 1

tstv_ratio = ts_count / tv_count if tv_count > 0 else float('inf')
```

## Key Concepts

- **Coordinate system**: pysam uses 0-based half-open (Python style). VCF files use 1-based.
- **Index files required**: BAM needs `.bai`, FASTA needs `.fai`, VCF.gz needs `.tbi`
- **File modes**: `"rb"` for BAM, `"r"` for SAM, `"wb"` for write BAM
