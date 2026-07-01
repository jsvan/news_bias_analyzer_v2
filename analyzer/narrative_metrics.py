"""
Computational kernels for the narrative-analysis roadmap
(docs/ROADMAP_IDEAS_2026.md §1–§6).

Pure functions over plain numpy arrays / dicts — no DB access. Each feature's
DB wiring (the SQL that produces these inputs) is written when the feature is
built; keeping the math dependency-free makes it testable anywhere:

    python -m analyzer.narrative_metrics   # runs the self-test

Conventions:
- sentiment scores are in [-2, +2] (power and moral dimensions)
- a "series" is a 1D np.array indexed by consecutive time windows (NaN = no data)
"""

import numpy as np

ARCHETYPES = {
    (True, True): "hero",       # strong + moral
    (True, False): "villain",   # strong + immoral
    (False, True): "victim",    # weak + moral
    (False, False): "nuisance", # weak + immoral
}


def archetype(power: float, moral: float, neutral_band: float = 0.25) -> str:
    """Quadrant of the power×moral plane; 'neutral' inside the center band."""
    if abs(power) < neutral_band and abs(moral) < neutral_band:
        return "neutral"
    return ARCHETYPES[(power >= 0, moral >= 0)]


def trajectory(power_series, moral_series, min_points: int = 3):
    """Per-window (power, moral) waypoints for one entity in one source.

    Returns list of (index, power, moral) for windows with data, or None if
    fewer than min_points — not enough to draw a path.
    """
    pts = [(i, p, m) for i, (p, m) in enumerate(zip(power_series, moral_series))
           if not (np.isnan(p) or np.isnan(m))]
    return pts if len(pts) >= min_points else None


def sentiment_histogram(scores, bins: int = 8, lo: float = -2.0, hi: float = 2.0):
    """Normalized histogram of sentiment scores (probability vector)."""
    hist, _ = np.histogram(np.clip(scores, lo, hi), bins=bins, range=(lo, hi))
    total = hist.sum()
    return hist / total if total else np.full(bins, 1.0 / bins)


def js_divergence(p, q) -> float:
    """Jensen–Shannon divergence between two probability vectors (base 2, in [0,1])."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    m = 0.5 * (p + q)

    def _kl(a, b):
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def contested_ranking(sphere_scores: dict, min_mentions: int = 10, bins: int = 8):
    """Rank entities by cross-sphere disagreement.

    sphere_scores: {entity: {sphere: [scores...]}}
    Returns [(entity, divergence)] sorted desc. Divergence = max pairwise JSD
    between spheres' histograms (max, not mean: one sharp disagreement is the
    story even if other spheres agree).
    """
    ranked = []
    for entity, spheres in sphere_scores.items():
        hists = [sentiment_histogram(s, bins) for s in spheres.values()
                 if len(s) >= min_mentions]
        if len(hists) < 2:
            continue
        worst = max(js_divergence(a, b)
                    for i, a in enumerate(hists) for b in hists[i + 1:])
        ranked.append((entity, worst))
    ranked.sort(key=lambda t: -t[1])
    return ranked


def salience_asymmetry(counts_a: int, counts_b: int, total_a: int, total_b: int) -> float:
    """Selection-bias signal: log2 ratio of an entity's mention *rate* between
    two spheres, +1-smoothed. 0 = equal attention; +3 ≈ 8x louder in sphere A."""
    rate_a = (counts_a + 1) / (total_a + 1)
    rate_b = (counts_b + 1) / (total_b + 1)
    return float(np.log2(rate_a / rate_b))


def lagged_correlation(series_a, series_b, max_lag: int = 4, n_permutations: int = 1000,
                       seed: int = 0):
    """Lead-lag between two sentiment-change series.

    Correlates diff(a) with diff(b) shifted by each lag in [-max_lag, +max_lag];
    positive best_lag means A leads B. Significance by permutation test (shuffle
    B's changes), which is the defensible alternative to Granger on short noisy
    series. Returns (best_lag, best_corr, p_value) or None if too little overlap.
    """
    da, db = np.diff(np.asarray(series_a, float)), np.diff(np.asarray(series_b, float))

    def _corr_at(x, y, lag):
        if lag > 0:
            x, y = x[:-lag or None], y[lag:]
        elif lag < 0:
            x, y = x[-lag:], y[:lag]
        mask = ~(np.isnan(x) | np.isnan(y))
        if mask.sum() < 5 or x[mask].std() == 0 or y[mask].std() == 0:
            return None
        return float(np.corrcoef(x[mask], y[mask])[0, 1])

    candidates = [(lag, c) for lag in range(-max_lag, max_lag + 1)
                  if (c := _corr_at(da, db, lag)) is not None]
    if not candidates:
        return None
    best_lag, best_corr = max(candidates, key=lambda t: abs(t[1]))

    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_permutations):
        perm = rng.permutation(db)
        cs = [c for lag in range(-max_lag, max_lag + 1)
              if (c := _corr_at(da, perm, lag)) is not None]
        if cs and max(abs(c) for c in cs) >= abs(best_corr):
            exceed += 1
    return best_lag, best_corr, (exceed + 1) / (n_permutations + 1)


def synchrony_score(change_matrix) -> float:
    """Coordination fingerprint for one entity in one cluster of sources.

    change_matrix: sources × windows array of sentiment *changes* (NaN ok).
    Score = |mean pairwise correlation| of the sources' change series, in [0, 1].
    Organic coverage ≈ low; a cluster pivoting together ≈ high.
    """
    m = np.asarray(change_matrix, float)
    corrs = []
    for i in range(m.shape[0]):
        for j in range(i + 1, m.shape[0]):
            mask = ~(np.isnan(m[i]) | np.isnan(m[j]))
            if mask.sum() < 5 or m[i][mask].std() == 0 or m[j][mask].std() == 0:
                continue
            corrs.append(np.corrcoef(m[i][mask], m[j][mask])[0, 1])
    return float(abs(np.mean(corrs))) if corrs else 0.0


def svd_source_map(matrix, n_dims: int = 2):
    """Empirical ideological axes from a source × entity sentiment matrix.

    NaN cells (source never covered entity) are filled with the entity's column
    mean after centering — i.e., they carry no signal. Returns
    (source_coords [n_sources × n_dims], entity_loadings [n_entities × n_dims],
    explained_variance_ratio).
    """
    m = np.asarray(matrix, float)
    col_mean = np.nanmean(m, axis=0)
    centered = m - col_mean
    centered[np.isnan(centered)] = 0.0
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    var = s ** 2
    return (u[:, :n_dims] * s[:n_dims],
            vt[:n_dims].T,
            var[:n_dims] / var.sum() if var.sum() else var[:n_dims])


def shrunk_means(cell_sums, cell_counts, prior_strength: float = 10.0):
    """Empirical-Bayes shrinkage for sparse entity×source cells.

    Cell means are pulled toward the global mean with weight prior_strength
    (in pseudo-mentions): shrunk = (sum + k*global) / (n + k). Cells with n=0
    return the global mean. prior_strength is the tunable knob.
    """
    sums, counts = np.asarray(cell_sums, float), np.asarray(cell_counts, float)
    total_n = counts.sum()
    global_mean = sums.sum() / total_n if total_n else 0.0
    return (sums + prior_strength * global_mean) / (counts + prior_strength)


def self_test():
    rng = np.random.default_rng(42)

    # archetype quadrants
    assert archetype(1.5, 1.2) == "hero" and archetype(1.5, -1.2) == "villain"
    assert archetype(-1.0, 1.0) == "victim" and archetype(-1.0, -1.0) == "nuisance"
    assert archetype(0.1, -0.1) == "neutral"

    # trajectory: NaN windows dropped, min_points respected
    t = trajectory([1, np.nan, 0.5, 0], [1, np.nan, -0.5, -1])
    assert t is not None and len(t) == 3 and t[0] == (0, 1, 1)
    assert trajectory([1, np.nan], [1, np.nan]) is None

    # JSD: identical = 0, disjoint = 1, symmetric
    a = sentiment_histogram(rng.normal(1.2, 0.3, 500))
    b = sentiment_histogram(rng.normal(-1.2, 0.3, 500))
    assert js_divergence(a, a) < 1e-12
    assert js_divergence(a, b) > 0.9
    assert abs(js_divergence(a, b) - js_divergence(b, a)) < 1e-12

    # contested ranking: the disputed entity outranks the agreed one
    ranked = contested_ranking({
        "disputed": {"west": list(rng.normal(1.5, 0.2, 50)),
                     "east": list(rng.normal(-1.5, 0.2, 50))},
        "agreed": {"west": list(rng.normal(0.5, 0.2, 50)),
                   "east": list(rng.normal(0.5, 0.2, 50))},
        "thin": {"west": [1.0], "east": [-1.0]},  # below min_mentions -> excluded
    })
    assert [e for e, _ in ranked] == ["disputed", "agreed"]

    # salience asymmetry: louder in A -> positive; equal -> ~0
    assert salience_asymmetry(80, 10, 1000, 1000) > 2.5
    assert abs(salience_asymmetry(50, 50, 1000, 1000)) < 0.01

    # lead-lag: B is A shifted by 2 windows -> A leads with lag +2, small p
    base = np.cumsum(rng.normal(0, 1, 60))
    res = lagged_correlation(base[2:], base[:-2], max_lag=4, n_permutations=200)
    assert res is not None
    lag, corr, p = res
    assert lag == 2 and corr > 0.9 and p < 0.05, (lag, corr, p)

    # synchrony: coordinated cluster >> independent cluster
    directive = rng.normal(0, 1, 40)
    coordinated = np.vstack([directive + rng.normal(0, 0.2, 40) for _ in range(5)])
    independent = np.vstack([rng.normal(0, 1, 40) for _ in range(5)])
    assert synchrony_score(coordinated) > 0.8
    assert synchrony_score(independent) < 0.3

    # SVD map: two blocs with opposite sentiment on bloc-defining entities
    # separate on dimension 1, despite NaN holes
    bloc = np.array([1, 1, 1, -1, -1, -1], float)
    m = np.outer(bloc, np.array([1.5, -1.5, 1.0])) + rng.normal(0, 0.1, (6, 3))
    m[0, 2] = np.nan
    coords, loadings, evr = svd_source_map(m)
    d1 = coords[:, 0]
    assert (d1[:3] > 0).all() != (d1[3:] > 0).all()  # blocs on opposite sides
    assert evr[0] > 0.8

    # shrinkage: n=1 outlier cell pulled hard toward global mean; n=1000 cell barely moves
    shrunk = shrunk_means([-2.0, 2000.0], [1, 1000], prior_strength=10.0)
    global_mean = 1998.0 / 1001
    assert abs(shrunk[0] - global_mean) < abs(-2.0 - global_mean) * 0.2
    assert abs(shrunk[1] - 2.0) < 0.01

    print("narrative_metrics self-test OK")


if __name__ == "__main__":
    self_test()
