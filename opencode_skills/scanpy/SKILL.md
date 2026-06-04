---
name: scanpy
description: "Single-cell RNA-seq analysis pipeline. Invoke for .h5ad data, QC, normalization, PCA/UMAP, clustering, marker genes, cell type annotation."
---

# Scanpy

Scalable Python toolkit for single-cell RNA-seq analysis, built on AnnData.

## When to Use

- Input is `.h5ad` file or 10X Genomics data
- Query mentions single-cell, scRNA-seq, clustering, UMAP, cell types, marker genes
- Need QC, normalization, dimensionality reduction, or trajectory analysis

## Quick Start

```python
import scanpy as sc
import numpy as np

sc.settings.verbosity = 3
sc.settings.set_figure_params(dpi=80, facecolor='white')

# Load data
adata = sc.read_h5ad('data.h5ad')
# or: adata = sc.read_10x_mtx('path/to/data/')
# or: adata = sc.read_csv('data.csv')
```

## AnnData Structure

```python
adata.X          # Expression matrix (cells × genes)
adata.obs        # Cell metadata (DataFrame)
adata.var        # Gene metadata (DataFrame)
adata.uns        # Unstructured annotations (dict)
adata.obsm       # Embeddings (PCA, UMAP)
adata.raw        # Raw data backup
```

## Standard Workflow

### 1. Quality Control

```python
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
adata = adata[adata.obs.pct_counts_mt < 5, :]
```

### 2. Normalize and Select Features

```python
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.raw = adata  # Save raw for later

sc.pp.highly_variable_genes(adata, n_top_genes=2000)
adata = adata[:, adata.var.highly_variable]

sc.pp.regress_out(adata, ['total_counts', 'pct_counts_mt'])
sc.pp.scale(adata, max_value=10)
```

### 3. Dimensionality Reduction

```python
sc.tl.pca(adata, svd_solver='arpack')
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)
sc.tl.umap(adata)
```

### 4. Clustering

```python
sc.tl.leiden(adata, resolution=0.5)
sc.pl.umap(adata, color='leiden')
```

### 5. Marker Genes

```python
sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')
sc.pl.rank_genes_groups(adata, n_genes=25)

# Get as DataFrame
markers = sc.get.rank_genes_groups_df(adata, group='0')
```

### 6. Cell Type Annotation

```python
sc.pl.dotplot(adata, var_names=marker_genes, groupby='leiden')

cluster_to_celltype = {'0': 'CD4 T cells', '1': 'Monocytes', '2': 'B cells'}
adata.obs['cell_type'] = adata.obs['leiden'].map(cluster_to_celltype)
```

## Common Tasks

### DE Between Conditions

```python
adata_sub = adata[adata.obs['cell_type'] == 'T cells']
sc.tl.rank_genes_groups(adata_sub, groupby='condition',
                         groups=['treated'], reference='control')
```

### Gene Set Scoring

```python
sc.tl.score_genes(adata, gene_list, score_name='my_score')
sc.pl.umap(adata, color='my_score')
```

### Trajectory / Pseudotime

```python
sc.tl.paga(adata, groups='leiden')
adata.uns['iroot'] = np.flatnonzero(adata.obs['leiden'] == '0')[0]
sc.tl.dpt(adata)
sc.pl.umap(adata, color='dpt_pseudotime')
```

### Batch Correction

```python
sc.pp.combat(adata, key='batch')
```

## Key Parameters

| Parameter | Typical Range | Effect |
|-----------|--------------|--------|
| `min_genes` | 200-500 | Min genes per cell for QC |
| `pct_counts_mt` | 5-20% | MT% threshold |
| `n_top_genes` | 2000-3000 | Highly variable genes |
| `n_pcs` | 30-50 | PCA dimensions (check elbow plot) |
| `n_neighbors` | 10-30 | Neighborhood graph |
| `resolution` | 0.3-1.2 | Clustering granularity (higher = more clusters) |

## Common Pitfalls

1. **Always save raw**: `adata.raw = adata` BEFORE subsetting to HVGs. Otherwise you lose gene expression data for plotting.

2. **Use `use_raw=True` for expression plots**: Plots should show original normalized counts, not scaled values.
   ```python
   sc.pl.umap(adata, color='CD3D', use_raw=True)
   ```

3. **Leiden > Louvain**: Prefer Leiden clustering — more robust and efficient.

4. **MT gene prefix varies by species**: Human = `MT-`, Mouse = `mt-`. Check with:
   ```python
   adata.var_names[adata.var_names.str.contains('^[Mm][Tt]-')]
   ```

5. **Resolution tuning**: Don't just use default. Try 0.3, 0.5, 0.8, 1.0 and compare:
   ```python
   for res in [0.3, 0.5, 0.8, 1.0]:
       sc.tl.leiden(adata, resolution=res, key_added=f'leiden_{res}')
   ```

6. **Check PCA variance**: Use `sc.pl.pca_variance_ratio(adata, log=True)` to pick `n_pcs`.

7. **Save intermediate results**: `adata.write('checkpoint.h5ad')` — long workflows can fail midway.
