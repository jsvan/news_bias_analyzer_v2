import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardHeader,
  CardContent,
  Chip,
  Autocomplete,
  TextField,
  CircularProgress,
  Grid,
} from '@mui/material';
import { tokens, categoricalColor, monoNumber } from '../theme';
import { similarityApi } from '../services/api';

// "Source space" - which sources see the world alike, from the data alone.
// Backed by the weekly Pearson matrix over common entities
// (analyzer/source_similarity.py kernels via /similarity/matrix). A pair below
// the 10-common-entities floor is absent - unknown, not zero - so a missing
// link means "not enough shared coverage to say", never "dissimilar".

interface MatrixSource {
  source_id: number;
  name: string;
  country: string | null;
  cluster: string | null;
  is_centroid: boolean;
}

interface MatrixPair {
  source_id_1: number;
  source_id_2: number;
  score: number;
  common_entities: number;
}

interface MatrixResponse {
  window_start: string | null;
  window_end: string | null;
  sources: MatrixSource[];
  pairs: MatrixPair[];
}

interface NeighborEntry {
  source_id: number;
  name: string;
  country: string | null;
  score: number;
  common_entities: number;
}

interface NeighborsResponse {
  source_id: number;
  source_name: string;
  window_start: string | null;
  window_end: string | null;
  nearest: NeighborEntry[];
  farthest: NeighborEntry[];
}

const scoreColor = (score: number): string =>
  score >= 0 ? tokens.accent : tokens.villain;

const NeighborRow: React.FC<{ entry: NeighborEntry }> = ({ entry }) => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      px: 2,
      py: 0.75,
      borderTop: `1px solid ${tokens.border}`,
    }}
  >
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="body2" sx={{ color: tokens.ink }} noWrap>
        {entry.name}
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
        {entry.country ?? 'Unknown'} · {entry.common_entities} shared entities
      </Typography>
    </Box>
    <Typography variant="body2" sx={{ ...monoNumber, color: scoreColor(entry.score), ml: 2 }}>
      {entry.score >= 0 ? '+' : ''}
      {entry.score.toFixed(2)}
    </Typography>
  </Box>
);

const SourceSpacePage: React.FC = () => {
  const [matrix, setMatrix] = useState<MatrixResponse | null>(null);
  const [matrixError, setMatrixError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MatrixSource | null>(null);
  const [neighbors, setNeighbors] = useState<NeighborsResponse | null>(null);
  const [neighborsLoading, setNeighborsLoading] = useState(false);

  useEffect(() => {
    similarityApi
      .getMatrix()
      .then((data: MatrixResponse) => setMatrix(data))
      .catch((err) => setMatrixError((err as Error).message));
  }, []);

  useEffect(() => {
    if (!selected) {
      setNeighbors(null);
      return;
    }
    setNeighborsLoading(true);
    similarityApi
      .getSourceNeighbors(selected.source_id, { limit: 5 })
      .then((data: NeighborsResponse) => setNeighbors(data))
      .catch(() => setNeighbors(null))
      .finally(() => setNeighborsLoading(false));
  }, [selected]);

  // Clusters with at least two members, largest first; the rest are sources
  // whose coverage didn't overlap enough with anyone to place them.
  const { clusters, unplaced, countryOrder } = useMemo(() => {
    const bySource = new Map<number, MatrixSource>();
    (matrix?.sources ?? []).forEach((s) => bySource.set(s.source_id, s));
    const groups = new Map<string, MatrixSource[]>();
    const loners: MatrixSource[] = [];
    (matrix?.sources ?? []).forEach((s) => {
      if (s.cluster) {
        const list = groups.get(s.cluster) ?? [];
        list.push(s);
        groups.set(s.cluster, list);
      }
    });
    const multi: MatrixSource[][] = [];
    groups.forEach((members) => {
      if (members.length >= 2) multi.push(members);
      else loners.push(...members);
    });
    multi.sort((a, b) => b.length - a.length);
    const order: string[] = [];
    (matrix?.sources ?? []).forEach((s) => {
      const c = s.country ?? 'Unknown';
      if (!order.includes(c)) order.push(c);
    });
    return { clusters: multi, unplaced: loners, countryOrder: order };
  }, [matrix]);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 0.5 }}>
        Source Space
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3, maxWidth: 720 }}>
        Which sources see the world alike. Every pair of sources is correlated on the moral
        scores they gave the entities both covered over the last month
        {matrix?.window_start ? ` (${matrix.window_start} to ${matrix.window_end})` : ''}. Groups
        below emerge from that correlation alone — no outlet is labeled anything; the data is
        allowed to cluster itself.
      </Typography>

      {matrixError && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              {matrixError}
            </Typography>
          </CardContent>
        </Card>
      )}

      {!matrix && !matrixError && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={28} />
        </Box>
      )}

      {matrix && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={7}>
            <Card>
              <CardHeader
                title="Constellations"
                subheader="Sources whose sentiment moves together, grouped by average correlation ≥ 0.5"
              />
              <CardContent sx={{ pt: 0 }}>
                {clusters.length === 0 && (
                  <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                    No multi-source groups in the current window — not enough overlapping
                    coverage yet.
                  </Typography>
                )}
                {clusters.map((members, idx) => (
                  <Box
                    key={members[0].cluster ?? idx}
                    sx={{
                      py: 1.5,
                      borderTop: idx === 0 ? 'none' : `1px solid ${tokens.border}`,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{ color: tokens.inkMuted, display: 'block', mb: 0.75 }}
                    >
                      Group {idx + 1} · {members.length} sources
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                      {members.map((m) => (
                        <Chip
                          key={m.source_id}
                          label={m.name}
                          size="small"
                          onClick={() => setSelected(m)}
                          variant={m.is_centroid ? 'filled' : 'outlined'}
                          sx={{
                            borderColor: categoricalColor(m.country ?? 'Unknown', countryOrder),
                            color: m.is_centroid ? '#fff' : tokens.ink,
                            bgcolor: m.is_centroid
                              ? categoricalColor(m.country ?? 'Unknown', countryOrder)
                              : 'transparent',
                          }}
                        />
                      ))}
                    </Box>
                  </Box>
                ))}
                {unplaced.length > 0 && (
                  <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mt: 2 }}>
                    {unplaced.length} sources shared too little coverage with any group to be
                    placed this window.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={5}>
            <Card>
              <CardHeader
                title="Nearest and farthest"
                subheader="Pick a source to see who reads the world most and least like it"
              />
              <CardContent sx={{ pt: 0 }}>
                <Autocomplete
                  options={matrix.sources}
                  getOptionLabel={(s) => s.name}
                  value={selected}
                  onChange={(_, v) => setSelected(v)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="Choose a source" size="small" />
                  )}
                  sx={{ mb: 1.5 }}
                />
                {neighborsLoading && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                    <CircularProgress size={22} />
                  </Box>
                )}
                {neighbors && !neighborsLoading && (
                  <>
                    <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                      MOST ALIKE
                    </Typography>
                    <Box sx={{ mb: 2 }}>
                      {neighbors.nearest.map((n) => (
                        <NeighborRow key={`n-${n.source_id}`} entry={n} />
                      ))}
                    </Box>
                    {neighbors.farthest.length > 0 && (
                      <>
                        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                          LEAST ALIKE
                        </Typography>
                        <Box>
                          {neighbors.farthest.map((n) => (
                            <NeighborRow key={`f-${n.source_id}`} entry={n} />
                          ))}
                        </Box>
                      </>
                    )}
                  </>
                )}
                {!selected && !neighborsLoading && (
                  <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                    Correlation says how similarly two sources scored the same entities; the
                    shared-entity count says how much overlap that judgment rests on.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      <Typography variant="caption" sx={{ display: 'block', mt: 3, color: tokens.inkMuted }}>
        Method: Pearson correlation of per-entity mean moral scores over entities both sources
        covered (minimum 10 shared); average-linkage clustering on 1 − r. Pairs with too little
        shared coverage are unknown, not zero, and are never drawn as disagreement.
      </Typography>
    </Box>
  );
};

export default SourceSpacePage;
