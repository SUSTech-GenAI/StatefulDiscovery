---
name: mygene
description: "Gene ID conversion and annotation. Invoke when you need to map between any gene identifier formats."
---

# MyGene

Python client for the MyGene.info API — fast gene ID mapping and annotation.

## When to Use

- Data has Ensembl IDs (ENSG..., ENSMUSG...) but you need gene symbols
- Data has RefSeq IDs (NM_..., NP_...) but you need gene symbols
- Data has Entrez IDs but you need symbols (or vice versa)
- Need gene annotations (GO terms, pathway membership, genomic position)
- Before running enrichment analysis (gseapy needs gene symbols)

## Quick Start

```python
import mygene
mg = mygene.MyGeneInfo()

# Single gene query
result = mg.getgene('ENSG00000141510', fields='symbol,name')
# → {'symbol': 'TP53', 'name': 'tumor protein p53', ...}

# Batch query (most common use case)
gene_ids = ['ENSG00000141510', 'ENSG00000012048', 'ENSG00000146648']
results = mg.querymany(gene_ids, scopes='ensembl.gene', fields='symbol,entrezgene', species='human')
```

## Batch ID Conversion

### Ensembl → Symbol (most common)

```python
import mygene
import pandas as pd

mg = mygene.MyGeneInfo()

# Your gene list (e.g., from DE results index)
ensembl_ids = df.index.tolist()

# Query
results = mg.querymany(
    ensembl_ids,
    scopes='ensembl.gene',
    fields='symbol',
    species='human',   # or 'mouse', 'rat', etc.
    as_dataframe=True
)

# Build mapping dict
id_map = results['symbol'].dropna().to_dict()

# Apply to your data
df['gene_symbol'] = df.index.map(id_map)
```

### Symbol → Entrez

```python
results = mg.querymany(
    gene_symbols,
    scopes='symbol',
    fields='entrezgene',
    species='human',
    as_dataframe=True
)
```

### RefSeq → Symbol

```python
results = mg.querymany(
    refseq_ids,        # e.g., ['NM_000546', 'NM_007294']
    scopes='refseq',
    fields='symbol',
    species='human',
    as_dataframe=True
)
```

### Entrez → Symbol

```python
results = mg.querymany(
    entrez_ids,
    scopes='entrezgene',
    fields='symbol',
    species='human',
    as_dataframe=True
)
```

## Key Parameters

| Parameter | Values | Purpose |
|-----------|--------|---------|
| `scopes` | `'ensembl.gene'`, `'symbol'`, `'entrezgene'`, `'refseq'` | Input ID type |
| `fields` | `'symbol'`, `'entrezgene'`, `'name'`, `'go'`, `'pathway.kegg'` | What to return |
| `species` | `'human'`, `'mouse'`, `'rat'`, or taxonomy ID (9606, 10090) | Organism filter |
| `as_dataframe` | `True` / `False` | Return DataFrame vs list of dicts |

## Detecting ID Types

```python
# Ensembl gene IDs
'ENSG00000141510'     # Human (ENSG)
'ENSMUSG00000059552'  # Mouse (ENSMUSG)

# Entrez IDs — plain integers
'7157'  # TP53

# Gene symbols — short uppercase names
'TP53', 'BRCA1', 'EGFR'

# RefSeq
'NM_000546'  # mRNA
'NP_000537'  # Protein
```

## Handling Common Issues

### Unmapped genes

```python
results = mg.querymany(ids, scopes='ensembl.gene', fields='symbol', species='human', as_dataframe=True)

# Check for unmapped
unmapped = results[results['notfound'] == True] if 'notfound' in results.columns else pd.DataFrame()
print(f"Mapped: {len(results) - len(unmapped)}, Unmapped: {len(unmapped)}")

# Use only mapped genes
mapped = results[results['symbol'].notna()]
```

### Duplicate mappings

```python
# Some IDs map to multiple genes — keep first match
results = results[~results.index.duplicated(keep='first')]
```

### Mouse gene symbols

Mouse genes use different capitalization (e.g., `Tp53` not `TP53`):

```python
results = mg.querymany(
    mouse_ensembl_ids,
    scopes='ensembl.gene',
    fields='symbol',
    species='mouse',  # Important: specify mouse
    as_dataframe=True
)
```

## Common Pitfalls

1. **Wrong species**: Always specify `species`. Ensembl IDs are species-specific (ENSG = human, ENSMUSG = mouse) but specifying the species avoids ambiguous matches.

2. **Version suffixes**: Ensembl IDs sometimes have versions (`ENSG00000141510.12`). Strip them:
   ```python
   clean_ids = [x.split('.')[0] for x in ensembl_ids]
   ```

3. **Network required**: mygene queries an online API. It will fail without network access.

4. **Large batches**: For >1000 genes, `querymany` handles batching automatically. No need to split manually.

5. **Mixed ID types**: If your data has mixed ID formats, detect the type first:
   ```python
   if ids[0].startswith('ENS'):
       scopes = 'ensembl.gene'
   elif ids[0].isdigit():
       scopes = 'entrezgene'
   else:
       scopes = 'symbol'
   ```

## Typical Workflow: DE Results → Enrichment

```python
import mygene
import gseapy as gp

mg = mygene.MyGeneInfo()

# 1. DE results have Ensembl IDs as index
de_results = pd.read_csv('deseq2_results.csv', index_col=0)

# 2. Map to symbols
clean_ids = [x.split('.')[0] for x in de_results.index]
mapped = mg.querymany(clean_ids, scopes='ensembl.gene', fields='symbol', species='human', as_dataframe=True)
id_map = mapped['symbol'].dropna().to_dict()

# 3. Get significant gene symbols
sig_genes = de_results[de_results['padj'] < 0.05].index
sig_symbols = [id_map[g.split('.')[0]] for g in sig_genes if g.split('.')[0] in id_map]

# 4. Run enrichment
enr = gp.enrichr(gene_list=sig_symbols, gene_sets='GO_Biological_Process_2021', organism='human')
```
