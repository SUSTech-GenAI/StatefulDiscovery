---
name: gseapy
description: "Gene set enrichment analysis (GSEA, Enrichr, over-representation). Invoke when query mentions enrichment, pathway analysis, GO analysis, GSEA, or gene set."
---

# GSEApy

Python wrapper for GSEA and Enrichr-style enrichment analysis.

## When to Use

- Query mentions "enrichment analysis", "pathway analysis", "GO enrichment", "GSEA"
- You have a list of genes (from DE analysis, clustering, etc.) and want biological interpretation
- Need to find enriched pathways, GO terms, or gene sets

## Three Main Functions

| Function | Input | When to Use |
|----------|-------|-------------|
| `gseapy.enrichr()` | Gene list (names only) | Over-representation analysis. You have a set of significant genes. |
| `gseapy.prerank()` | Ranked gene list (name + score) | Pre-ranked GSEA. You have ALL genes with a ranking metric (e.g., log2FC, -log10p × sign). |
| `gseapy.gsea()` | Expression matrix + phenotype labels | Full GSEA. You have raw expression data + sample groups. |

**Critical**: `enrichr()` and `prerank()` answer DIFFERENT questions. Do not confuse them.

## enrichr() — Over-Representation Analysis

Use when you have a **list of significant genes** (e.g., DE genes with padj < 0.05).

```python
import gseapy as gp

# Input: a plain list of gene symbols
gene_list = ["BRCA1", "TP53", "CDK2", "MYC", "EGFR"]

enr = gp.enrichr(
    gene_list=gene_list,
    gene_sets='GO_Biological_Process_2021',  # or multiple: ['KEGG_2021_Human', 'GO_BP_2021']
    organism='human',
    outdir=None,  # set path to save results
    cutoff=0.05
)

# Results
enr.results  # DataFrame with Term, Overlap, P-value, Adjusted P-value, Genes
significant = enr.results[enr.results['Adjusted P-value'] < 0.05]
```

### Common Gene Set Libraries

```python
# List all available libraries
gp.get_library_name(organism='human')

# Commonly used:
'GO_Biological_Process_2021'
'GO_Molecular_Function_2021'
'GO_Cellular_Component_2021'
'KEGG_2021_Human'
'Reactome_2022'
'MSigDB_Hallmark_2020'
'WikiPathways_2019_Human'
```

## prerank() — Pre-Ranked GSEA

Use when you have **all genes ranked by a metric** (not just significant ones).

```python
import pandas as pd
import gseapy as gp

# Input: DataFrame or Series with gene names as index, ranking metric as values
# Common ranking: -log10(pvalue) * sign(log2FC)
import numpy as np
rnk = pd.DataFrame({
    'gene': results.index,
    'score': -np.log10(results['pvalue']) * np.sign(results['log2FoldChange'])
}).dropna()

pre_res = gp.prerank(
    rnk=rnk,
    gene_sets='GO_Biological_Process_2021',
    min_size=15,
    max_size=500,
    permutation_num=1000,
    outdir=None,
    seed=42
)

# Results
pre_res.res2d  # DataFrame with es, nes, pval, fdr
significant = pre_res.res2d[pre_res.res2d['fdr'] < 0.25]  # GSEA uses FDR < 0.25 convention
```

### Ranking Metric Tips

```python
# Option 1: signed -log10(p)
rnk['score'] = -np.log10(rnk['pvalue']) * np.sign(rnk['log2FoldChange'])

# Option 2: log2FC directly (simpler but less sensitive)
rnk['score'] = rnk['log2FoldChange']

# Option 3: t-statistic or Wald statistic from DE analysis
rnk['score'] = rnk['stat']
```

**Important**: Remove NaN/Inf values and duplicate genes before running.

```python
rnk = rnk.replace([np.inf, -np.inf], np.nan).dropna()
rnk = rnk.drop_duplicates(subset='gene')
```

## gsea() — Full GSEA

Use when you have raw expression data and sample labels.

```python
# Input: genes × samples expression matrix
gs_res = gp.gsea(
    data=expression_df,        # genes × samples
    gene_sets='KEGG_2021_Human',
    cls=class_vector,          # phenotype labels, e.g., ['control','control','treated','treated']
    min_size=15,
    max_size=500,
    permutation_num=1000,
    outdir=None
)
```

## Using Local Gene Set Files (.gmt)

```python
# If you have a .gmt file in the data directory
enr = gp.enrichr(gene_list=genes, gene_sets='path/to/geneset.gmt')
pre_res = gp.prerank(rnk=rnk, gene_sets='path/to/geneset.gmt')
```

## Common Pitfalls

1. **enrichr() vs prerank() confusion**: `enrichr()` takes a gene LIST (just names). `prerank()` takes a RANKED list (names + scores). Using the wrong one gives meaningless results.

2. **Gene symbol format**: GSEApy expects standard gene symbols (e.g., "TP53", not "ENSG00000141510"). Convert Ensembl IDs first using `mygene` (invoke `/mygene` skill).

3. **enrichr() needs internet**: `enrichr()` queries the Enrichr web API. If it fails, check network. Alternative: use local `.gmt` files with `prerank()`.

4. **prerank() input format**: Must be a DataFrame with exactly 2 columns (gene, score) or a Series with gene names as index. NOT a full DE results table.
   ```python
   # WRONG: passing full results
   gp.prerank(rnk=results, ...)

   # RIGHT: extract gene + score only
   rnk = results[['log2FoldChange']].dropna()
   gp.prerank(rnk=rnk, ...)
   ```

5. **Duplicate genes**: `prerank()` will fail or give wrong results with duplicate gene names. Always deduplicate:
   ```python
   rnk = rnk[~rnk.index.duplicated(keep='first')]
   ```

6. **FDR threshold for GSEA**: Convention is FDR < 0.25 (not 0.05). This is because GSEA is inherently more conservative.

7. **min_size / max_size**: Filter gene sets by size. Very small (<15) or very large (>500) gene sets are usually uninformative.
