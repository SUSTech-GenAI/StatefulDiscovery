---
name: pydeseq2
description: "Differential expression analysis for RNA-seq count data. Invoke when query mentions DESeq2, differential expression, DE genes, or RNA-seq comparison."
---

# PyDESeq2

Python implementation of DESeq2 for differential expression analysis with bulk RNA-seq data.

## When to Use

- Query mentions "DESeq2", "differential expression", "DE genes"
- Comparing gene expression between conditions (treated vs control)
- Multi-factor designs with batch effects or covariates
- Input is a count matrix (raw integer counts, NOT normalized)

## Quick Start

```python
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# 1. Load data — counts must be samples × genes (transpose if needed)
counts_df = pd.read_csv("counts.csv", index_col=0).T
metadata = pd.read_csv("metadata.csv", index_col=0)

# 2. Filter low-count genes
genes_to_keep = counts_df.columns[counts_df.sum(axis=0) >= 10]
counts_df = counts_df[genes_to_keep]

# 3. Fit DESeq2
dds = DeseqDataSet(
    counts=counts_df,
    metadata=metadata,
    design="~condition",
    refit_cooks=True
)
dds.deseq2()

# 4. Statistical testing
ds = DeseqStats(dds, contrast=["condition", "treated", "control"])
ds.summary()

# 5. Results
results = ds.results_df
significant = results[results.padj < 0.05]
```

## Design Formulas

```python
# Single factor
design = "~condition"

# Multi-factor (batch correction)
design = "~batch + condition"

# Continuous covariate
design = "~age + condition"

# Interaction
design = "~group + condition + group:condition"
```

**Rule**: put adjustment variables (batch, age) BEFORE the variable of interest.

## Contrast Specification

Format: `[variable, test_level, reference_level]`

```python
# treated vs control
ds = DeseqStats(dds, contrast=["condition", "treated", "control"])

# Multiple comparisons
for treatment in ["A", "B", "C"]:
    ds = DeseqStats(dds, contrast=["condition", treatment, "control"])
    ds.summary()
```

## Result Columns

| Column | Meaning |
|--------|---------|
| `baseMean` | Mean normalized count across samples |
| `log2FoldChange` | Log2 fold change between conditions |
| `lfcSE` | Standard error of LFC |
| `stat` | Wald test statistic |
| `pvalue` | Raw p-value |
| `padj` | BH-adjusted p-value (use this for significance) |

## LFC Shrinkage

```python
ds.lfc_shrink()  # apeGLM shrinkage
```

Use shrunk LFC for **visualization and ranking only**. P-values are unchanged.

## Common Pitfalls

1. **Data orientation**: Count matrices often load as genes × samples. You MUST transpose to samples × genes with `.T`.

2. **Index mismatch**: Sample names in counts and metadata must match exactly.
   ```python
   common = counts_df.index.intersection(metadata.index)
   counts_df = counts_df.loc[common]
   metadata = metadata.loc[common]
   ```

3. **Non-integer counts**: PyDESeq2 requires raw counts. Do NOT pass TPM, FPKM, or normalized values.

4. **Design not full rank**: Happens when variables are confounded. Check with:
   ```python
   pd.crosstab(metadata.condition, metadata.batch)
   ```

5. **Continuous covariates**: Ensure numeric type:
   ```python
   metadata["age"] = pd.to_numeric(metadata["age"])
   ```

6. **Use `padj`, not `pvalue`**: Always filter by adjusted p-value for multiple testing correction.

## Filtering Results

```python
# Significant genes
sig = results[results.padj < 0.05]

# With effect size filter
sig_large = results[(results.padj < 0.05) & (abs(results.log2FoldChange) > 1)]

# Up/down regulated
up = sig[sig.log2FoldChange > 0]
down = sig[sig.log2FoldChange < 0]
```
