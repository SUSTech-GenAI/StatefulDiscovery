---
name: phylogenetics
description: "Phylogenetic analysis: multiple sequence alignment (MAFFT), tree building (IQ-TREE, FastTree), tree metrics (treeness, branch lengths, patristic distances). Invoke when query involves phylogenetic trees, evolutionary analysis, sequence alignment, treeness, or tree statistics."
---

# Phylogenetics

Pipeline: MAFFT (alignment) → IQ-TREE 2 / FastTree (tree inference) → ETE3 (analysis).

## When to Use

- Multiple sequence alignment
- Phylogenetic tree building (ML, NJ)
- Tree statistics: treeness, branch lengths, patristic distances, tree length
- Comparative evolutionary analysis across taxa

## Installation

```bash
# These are pre-installed in the container via conda
# mafft, iqtree are available as CLI tools
# If needed:
conda install -c bioconda mafft iqtree fasttree
pip install ete3
```

## Alignment with MAFFT

```bash
# Auto-select method (recommended)
mafft --auto --thread 4 input.fasta > aligned.fasta

# Accurate (small datasets < 200 seqs)
mafft --localpair --maxiterate 1000 input.fasta > aligned.fasta

# Fast (large datasets > 1000 seqs)
mafft --retree 2 --thread 4 input.fasta > aligned.fasta
```

## Tree Building with IQ-TREE

```bash
# Auto model selection + ultrafast bootstrap
iqtree2 -s aligned.fasta -m TEST -B 1000 -T 4 --prefix output

# Output files:
# output.treefile  — Newick tree
# output.iqtree    — Full report (contains tree statistics)
# output.log       — Model selection details
```

## Key Tree Metrics from IQ-TREE Output

The `.iqtree` file contains important statistics:

```
Total tree length (sum of branch lengths): 3.1557
Sum of internal branch lengths: 1.5234 (48.26% of tree length)
```

- **Tree length**: Sum of all branch lengths
- **Treeness** (stemminess): `Sum of internal branch lengths / Total tree length` — proportion of tree length on internal branches. Higher = more phylogenetic signal.
- **Internal branch %**: The percentage in parentheses IS the treeness value

## Parsing IQ-TREE Output

```python
import re

def parse_iqtree_stats(iqtree_file):
    """Extract tree statistics from .iqtree output file."""
    stats = {}
    with open(iqtree_file) as f:
        content = f.read()

    # Total tree length
    m = re.search(r'Total tree length \(sum of branch lengths\): ([\d.]+)', content)
    if m:
        stats['tree_length'] = float(m.group(1))

    # Internal branch lengths and treeness
    m = re.search(r'Sum of internal branch lengths: ([\d.]+) \(([\d.]+)% of tree length\)', content)
    if m:
        stats['internal_branch_length'] = float(m.group(1))
        stats['treeness_pct'] = float(m.group(2))
        stats['treeness'] = float(m.group(2)) / 100  # as proportion

    return stats
```

## Tree Analysis with ETE3

```python
from ete3 import Tree

t = Tree("output.treefile")

# Basic stats
leaves = t.get_leaves()
print(f"Leaves: {len(leaves)}")
print(f"Total branch length: {sum(n.dist for n in t.traverse())}")

# Patristic distance (between two leaves)
d = t.get_distance("leaf1", "leaf2")

# Midpoint rooting
t.set_outgroup(t.get_midpoint_outgroup())

# Prune to subset
t.prune(["leaf1", "leaf2", "leaf3"], preserve_branch_length=True)
```

## FastTree (for large datasets > 5000 seqs)

```bash
# Nucleotide
FastTree -nt -gtr aligned.fasta > tree.nwk

# Protein
FastTree -lg aligned.fasta > tree.nwk
```

## Common Pitfalls

- **Alignment quality**: Poor alignment → unreliable tree. Always check alignment.
- **Model selection**: Use `-m TEST` to let IQ-TREE auto-select; don't guess.
- **Rooting**: Unrooted trees can be misleading. Use outgroup or midpoint rooting.
