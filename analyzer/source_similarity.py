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


def significance_weight(common, full: int = 50):
    """Confidence weight in [0, 1] for correlations estimated over shared entities.

    A correlation over 12 shared entities and one over 300 are not equally
    trustworthy, but past the min_common floor they'd otherwise carry equal
    weight. Standard recommender-system significance weighting: linear ramp
    reaching 1 at `full` shared entities. Used to damp thin-overlap pairs in
    clustering and in the MDS map's weights - the stored/displayed r stays raw
    (it's always shown alongside its shared-entity count).
    """
    return np.clip(np.asarray(common, float) / full, 0.0, 1.0)


def weighted_mds(dist, weights, n_dims: int = 2, n_iter: int = 500, tol: float = 1e-9):
    """Weighted MDS (SMACOF): embed points so pairwise distances match `dist`.

    This is the exclusion-tolerant replacement for factoring the source x entity
    matrix directly (narrative_metrics.svd_source_map): it consumes only the
    pairwise distances, so a source's coverage of entities nobody else touched
    never enters - no NaN filling, no shrink-to-origin artifact for sources
    with narrow shared coverage.

    Args:
        dist: n x n symmetric target distances; NaN = unknown pair.
        weights: n x n nonnegative confidence per pair (e.g.
            significance_weight of common-entity counts). Unknown pairs are
            forced to weight 0 regardless. Every point should have at least
            one positive weight or its position is arbitrary - callers drop
            such points first.
        n_dims: embedding dimensions.

    Deterministic: initialized from classical (Torgerson) MDS with unknown
    distances filled by the mean known distance, then Guttman-transform
    iterations. Output is centered, rotated to principal axes, and
    sign-canonicalized (the largest-|coordinate| point on each axis is
    positive), so identical input yields identical output.

    Returns (coords [n x n_dims], stress1, axis_variance_share) where stress1
    is Kruskal's stress-1 over the known pairs (0 = distances reproduced
    exactly; < ~0.15 is conventionally a good fit) and axis_variance_share is
    each axis's share of the embedding's variance (how elongated the map is).
    """
    d = np.asarray(dist, float).copy()
    n = d.shape[0]
    w = np.where(np.isfinite(d), np.asarray(weights, float), 0.0)
    np.fill_diagonal(w, 0.0)
    d = np.where(w > 0, d, 0.0)  # zero-weight cells are never consulted
    if n < 3:
        return np.zeros((n, n_dims)), 0.0, np.zeros(n_dims)

    # Deterministic init: Torgerson double-centering on the filled matrix.
    fill = d[w > 0].mean() if (w > 0).any() else 1.0
    dfull = np.where(w > 0, d, fill)
    np.fill_diagonal(dfull, 0.0)
    dfull = (dfull + dfull.T) / 2.0
    centerer = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * centerer @ (dfull ** 2) @ centerer
    evals, evecs = np.linalg.eigh(gram)
    top = np.argsort(evals)[::-1][:n_dims]
    coords = evecs[:, top] * np.sqrt(np.clip(evals[top], 0.0, None))

    # SMACOF: repeat the Guttman transform until stress stops improving.
    v_pinv = np.linalg.pinv(np.diag(w.sum(axis=1)) - w)
    prev_stress = None
    for _ in range(n_iter):
        delta = coords[:, None, :] - coords[None, :, :]
        embedded = np.sqrt((delta ** 2).sum(axis=-1))
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(embedded > 0, d / embedded, 0.0)
        b = -w * ratio
        np.fill_diagonal(b, 0.0)
        np.fill_diagonal(b, -b.sum(axis=1))
        coords = v_pinv @ (b @ coords)
        stress = float((w * (embedded - d) ** 2).sum())
        if prev_stress is not None and abs(prev_stress - stress) < tol * max(prev_stress, 1e-12):
            break
        prev_stress = stress

    delta = coords[:, None, :] - coords[None, :, :]
    embedded = np.sqrt((delta ** 2).sum(axis=-1))
    denom = float((w * d ** 2).sum())
    stress1 = float(np.sqrt((w * (embedded - d) ** 2).sum() / denom)) if denom > 0 else 0.0

    # Canonical orientation: center, principal axes, deterministic signs.
    coords = coords - coords.mean(axis=0)
    u, s, _vt = np.linalg.svd(coords, full_matrices=False)
    coords = u * s
    for k in range(coords.shape[1]):
        if coords[int(np.argmax(np.abs(coords[:, k]))), k] < 0:
            coords[:, k] = -coords[:, k]
    var = coords.var(axis=0)
    share = var / var.sum() if var.sum() else var
    return coords, stress1, share


def dividing_entities(matrix, labels, min_group_sources: int = 2,
                      min_groups: int = 2, ridge: float = 0.05,
                      min_f: float = 3.0):
    """Entities that best separate the clusters: support-weighted group spread.

    The substance behind the sociology - the constellations say WHO groups
    together; this ranks WHAT they disagree about. For each entity (column),
    consider the clusters with >= min_group_sources scored sources; if at
    least min_groups qualify, compute a one-way ANOVA:

    - Rank = msb, the between-group mean square (support-weighted spread of
      the group means): pure effect size, so a wide split backed by many
      sources beats a small gap. Ranking by F instead lets any two unanimous
      groups top the list on a trivial gap - integer per-cell scores make
      zero within-variance routine (measured 2026-08-19: Jared Leto at
      -2.00 vs -1.00 outranked the Communist Party of China's ±1 split).
    - Filter = F >= min_f (with `ridge` added to the within-group mean
      square), so msb still can't promote splits that are just noise.

    Args:
        matrix: sources x entities, NaN = no coverage.
        labels: per-source int group label; negative = ignore that source.

    Returns [(entity_col, f, msb, {label: group_mean}, {label: group_n})],
    sorted by msb descending. Entities without min_groups qualifying groups,
    or below min_f, are omitted.
    """
    m = np.asarray(matrix, float)
    lab = np.asarray(labels, int)
    groups = sorted({l for l in lab if l >= 0})
    out = []
    for col in range(m.shape[1]):
        means, counts, values = {}, {}, {}
        for g in groups:
            v = m[(lab == g), col]
            v = v[~np.isnan(v)]
            if len(v) >= min_group_sources:
                means[g] = float(v.mean())
                counts[g] = len(v)
                values[g] = v
        if len(means) < min_groups:
            continue
        all_v = np.concatenate(list(values.values()))
        grand = all_v.mean()
        ssb = sum(counts[g] * (means[g] - grand) ** 2 for g in means)
        ssw = sum(float(((values[g] - means[g]) ** 2).sum()) for g in means)
        dfb = len(means) - 1
        dfw = len(all_v) - len(means)
        msw = ssw / dfw if dfw > 0 else 0.0
        msb = ssb / dfb
        f = msb / (msw + ridge)
        if f < min_f:
            continue
        out.append((col, float(f), float(msb), means, counts))
    out.sort(key=lambda t: -t[2])
    return out


def seriation(corr, common, full: int = 50):
    """Leaf order + merge tree for the similarity heatmap and dendrogram.

    Average-linkage on 1 - significance-weighted r — the identical geometry
    cluster_by_correlation cuts into flat clusters — refined with scipy's
    optimal leaf ordering so the heatmap's diagonal runs along the smoothest
    similarity gradient and cluster blocks come out contiguous.

    Returns (order, merges): order is a list of leaf indices (row order for
    the seriated heatmap); merges is the linkage in scipy convention - the
    i-th entry (left, right, distance) merges nodes where an index < n is a
    leaf and index n+j refers to merges[j] - enough to rebuild the dendrogram.
    """
    from scipy.cluster.hierarchy import linkage, optimal_leaf_ordering, leaves_list
    from scipy.spatial.distance import squareform

    c = np.asarray(corr, float) * significance_weight(common, full=full)
    n = c.shape[0]
    if n < 2:
        return list(range(n)), []
    dist = 1.0 - c
    dist[np.isnan(dist)] = 2.0
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0  # exact symmetry for squareform
    condensed = squareform(dist, checks=False)
    z = optimal_leaf_ordering(linkage(condensed, method="average"), condensed)
    return ([int(i) for i in leaves_list(z)],
            [(int(a), int(b), float(d)) for a, b, d, _ in z])


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

    # 7. Significance weight ramps linearly and saturates at `full`.
    w = significance_weight([0, 25, 50, 500], full=50)
    assert np.allclose(w, [0.0, 0.5, 1.0, 1.0]), w

    # 8. Weighted MDS reproduces a genuinely planar configuration (stress ~ 0)
    #    and is deterministic.
    pts = rng.normal(0, 1, (8, 2))
    d8 = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
    x1, stress1, share = weighted_mds(d8, np.ones((8, 8)))
    x2, _, _ = weighted_mds(d8, np.ones((8, 8)))
    assert stress1 < 0.01, stress1
    assert np.allclose(x1, x2), "weighted_mds must be deterministic"
    assert np.isclose(share.sum(), 1.0) and share[0] >= share[1], share
    e8 = np.sqrt(((x1[:, None, :] - x1[None, :, :]) ** 2).sum(-1))
    assert np.allclose(e8, d8, atol=0.05), np.abs(e8 - d8).max()

    # 9. The exclusion property, end to end: A covers a superset of what B and
    #    C cover, but scores the shared entities identically - A must embed on
    #    top of B/C, and far from the inverted source D. (The old SVD map
    #    shrank A toward the origin for its unshared coverage.)
    shared = rng.normal(0, 1, 60)
    extra = rng.normal(0, 1, 40)
    a_full = np.concatenate([shared, extra])
    b_sub = np.concatenate([shared, np.full(40, np.nan)])
    d_inv = np.concatenate([-shared, np.full(40, np.nan)])
    m9 = np.vstack([a_full, b_sub, b_sub, d_inv])
    corr9, common9 = pairwise_pearson(m9, min_common=10)
    dist9 = 1.0 - corr9
    w9 = significance_weight(common9)
    x9, _, _ = weighted_mds(dist9, w9)
    d_ab = np.linalg.norm(x9[0] - x9[1])
    d_ad = np.linalg.norm(x9[0] - x9[3])
    assert d_ab < 0.1 * d_ad, (d_ab, d_ad)

    # 10. An unknown pair (weight 0) neither crashes nor produces NaN coords.
    dist10 = dist9.copy()
    dist10[0, 3] = dist10[3, 0] = np.nan
    x10, s10, _ = weighted_mds(dist10, w9)
    assert np.isfinite(x10).all() and np.isfinite(s10)

    # 11. Seriation makes correlation blocks contiguous and returns a full
    #     merge tree. m5 = [base, blockA, -base, blockB, sparse]: rows {0,1}
    #     and {2,3} must be adjacent in the order; the unknown row floats free.
    corr11, common11 = pairwise_pearson(m5, min_common=10)
    order, merges = seriation(corr11, common11)
    assert sorted(order) == [0, 1, 2, 3, 4], order
    pos = {leaf: i for i, leaf in enumerate(order)}
    assert abs(pos[0] - pos[1]) == 1, order
    assert abs(pos[2] - pos[3]) == 1, order
    assert len(merges) == 4 and all(len(m) == 3 for m in merges), merges

    # 12. Dividing entities: the sharply split column survives the F filter
    #     and reports its group means; the near-unanimous column is filtered
    #     as noise, the single-group column is omitted, and ignored sources
    #     (label -1) don't contribute.
    m12 = np.array([
        # split   agree  onegroup
        [+1.0,    0.50,  0.3],
        [+0.9,    0.55,  0.4],
        [-1.0,    0.50,  np.nan],
        [-0.9,    0.45,  np.nan],
        [+9.0,    9.00,  9.0],   # label -1: must be invisible
    ])
    ranked = dividing_entities(m12, [0, 0, 1, 1, -1])
    assert [t[0] for t in ranked] == [0], ranked
    assert ranked[0][3][0] > 0.9 and ranked[0][3][1] < -0.9, ranked[0][3]
    assert ranked[0][4] == {0: 2, 1: 2}, ranked[0][4]

    # 13. Rank is effect size, not F: a wide well-supported split must beat a
    #     small unanimous gap even though the latter has (near-)zero
    #     within-variance and therefore the larger F.
    wide = np.concatenate([np.array([2.0, 1.0, 3.0, -2.0, -1.0, -3.0]),
                           np.full(2, np.nan)])
    tiny = np.concatenate([np.full(6, np.nan), np.array([-2.0, 0.0])])
    m13 = np.column_stack([wide, tiny])
    labels13 = [0, 0, 0, 1, 1, 1, 2, 3]
    ranked13 = dividing_entities(m13, labels13, min_group_sources=1)
    assert [t[0] for t in ranked13] == [0, 1], ranked13
    assert ranked13[0][2] > ranked13[1][2], "wide split must outrank tiny gap"
    assert ranked13[1][1] > ranked13[0][1], "the tiny unanimous gap has the larger F"

    print("source_similarity self-test: all assertions passed")


if __name__ == "__main__":
    self_test()
