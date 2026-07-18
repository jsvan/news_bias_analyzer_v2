"""
Source-similarity kernels (todo.txt items 1-5; docs/STATE_OF_PROJECT_2026.md's
"highest-value unbuilt feature").

Pure functions over plain numpy arrays - no DB access, same convention as
analyzer/narrative_metrics.py. The DB wiring lives in
clustering/source_similarity.py (weekly job) and
server/routers/similarity_endpoints.py (API):

    python -m analyzer.source_similarity   # runs the self-test

The core object is a source x entity matrix of mean sentiment scores with NaN
holes (source never covered entity). Correlation is computed pairwise-complete:
each source pair is compared only on the entities BOTH covered, and pairs
sharing fewer than `min_common` entities get NaN (not 0 - "we don't know" is
different from "uncorrelated"). This differs deliberately from
narrative_metrics.svd_source_map, which must fill NaN holes to factor the whole
matrix at once; here no fill is needed, so none is done.
"""

import numpy as np


def pairwise_pearson(matrix, min_common: int = 10):
    """Pairwise-complete Pearson correlation between the rows of a matrix.

    Args:
        matrix: 2D array-like, sources x entities, NaN where a source never
            scored an entity.
        min_common: minimum number of entities two sources must share for
            their correlation to be reported (the project's min_mentions=10
            convention applied to common-entity counts).

    Returns:
        (corr, common): two n_sources x n_sources arrays. corr[i, j] is the
        Pearson correlation of rows i and j over their common entities (NaN if
        fewer than min_common, or if either side has zero variance on the
        common set). common[i, j] is the number of shared entities. The
        diagonal is corr=1.0, common=row's own coverage.
    """
    m = np.asarray(matrix, float)
    n = m.shape[0]
    corr = np.full((n, n), np.nan)
    common = np.zeros((n, n), dtype=int)
    present = ~np.isnan(m)

    for i in range(n):
        corr[i, i] = 1.0
        common[i, i] = int(present[i].sum())
        for j in range(i + 1, n):
            both = present[i] & present[j]
            k = int(both.sum())
            common[i, j] = common[j, i] = k
            if k < min_common:
                continue
            a, b = m[i, both], m[j, both]
            sa, sb = a.std(), b.std()
            if sa == 0 or sb == 0:
                continue  # a flat vector carries no shape to correlate
            r = float(np.corrcoef(a, b)[0, 1])
            corr[i, j] = corr[j, i] = r
    return corr, common


def cluster_by_correlation(corr, threshold: float = 0.5):
    """Average-linkage agglomerative clustering on distance = 1 - correlation.

    Pairs with unknown correlation (NaN) are treated as maximally distant
    (distance 2.0, i.e. correlation -1) so lack of overlap never glues two
    sources together. Clusters are cut where average linkage distance exceeds
    1 - threshold, so members of a cluster correlate >= threshold on average.

    Returns an array of integer labels (0-based, relabeled by cluster size,
    largest cluster first). Singletons get their own label.
    """
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform

    c = np.asarray(corr, float)
    n = c.shape[0]
    if n == 1:
        return np.zeros(1, dtype=int)
    dist = 1.0 - c
    dist[np.isnan(dist)] = 2.0
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0  # exact symmetry for squareform
    labels = fcluster(linkage(squareform(dist, checks=False), method="average"),
                      t=1.0 - threshold, criterion="distance")
    # Relabel by descending cluster size so label 0 is always the biggest.
    order = sorted(set(labels), key=lambda l: (-np.sum(labels == l), l))
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[l] for l in labels], dtype=int)


def neighbor_ranking(corr_row, self_index: int):
    """Indices of a source's neighbors sorted nearest-first, NaN pairs dropped.

    Returns a list of (index, correlation) excluding self and unknowns; the
    caller takes the head for "sees the world most alike" and the tail for
    "least alike".
    """
    row = np.asarray(corr_row, float)
    pairs = [(i, float(r)) for i, r in enumerate(row)
             if i != self_index and not np.isnan(r)]
    return sorted(pairs, key=lambda p: -p[1])


def self_test():
    """Assert kernel behavior on synthetic fixtures; exits nonzero on failure."""
    rng = np.random.default_rng(7)

    # 1. A source correlates perfectly with itself and its clone.
    base = rng.normal(0, 1, 40)
    m = np.vstack([base, base, -base])
    corr, common = pairwise_pearson(m, min_common=10)
    assert np.isclose(corr[0, 1], 1.0), corr[0, 1]
    assert np.isclose(corr[0, 2], -1.0), corr[0, 2]
    assert common[0, 1] == 40

    # 2. Below the common-entity floor -> NaN, not a number.
    sparse = np.full(40, np.nan)
    sparse[:5] = base[:5]
    m2 = np.vstack([base, sparse])
    corr2, common2 = pairwise_pearson(m2, min_common=10)
    assert common2[0, 1] == 5
    assert np.isnan(corr2[0, 1])

    # 3. Zero variance on the common set -> NaN (flat vector has no shape).
    flat = np.zeros(40)
    corr3, _ = pairwise_pearson(np.vstack([base, flat]), min_common=10)
    assert np.isnan(corr3[0, 1])

    # 4. Independent noise correlates near zero (|r| < 0.35 at n=200).
    a, b = rng.normal(0, 1, 200), rng.normal(0, 1, 200)
    corr4, _ = pairwise_pearson(np.vstack([a, b]), min_common=10)
    assert abs(corr4[0, 1]) < 0.35, corr4[0, 1]

    # 5. Clustering separates two blocks and isolates the unknown.
    blockA = base + rng.normal(0, 0.1, 40)
    blockB = -base + rng.normal(0, 0.1, 40)
    m5 = np.vstack([base, blockA, -base, blockB, sparse])
    corr5, _ = pairwise_pearson(m5, min_common=10)
    labels = cluster_by_correlation(corr5, threshold=0.5)
    assert labels[0] == labels[1], labels
    assert labels[2] == labels[3], labels
    assert labels[0] != labels[2], labels
    assert labels[4] not in (labels[0], labels[2]), labels

    # 6. Neighbor ranking is nearest-first and drops unknowns.
    ranked = neighbor_ranking(corr5[0], 0)
    assert ranked[0][0] == 1 and ranked[-1][0] in (2, 3), ranked
    assert all(i != 4 for i, _ in ranked), ranked

    print("source_similarity self-test: all assertions passed")


if __name__ == "__main__":
    self_test()
