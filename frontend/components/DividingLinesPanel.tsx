import React, { useEffect, useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  CircularProgress,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import { tokens, monoNumber } from '../theme';
import { similarityApi } from '../services/api';

// The substance behind the sociology: the constellations say WHO groups
// together; this table shows WHAT they disagree about. Rows are the entities
// that best separate the top constellations (support-weighted between-group
// spread, F-filtered against noise - see analyzer/source_similarity.py::
// dividing_entities), columns are the groups in the constellations panel's
// own numbering, cells are each bloc's mean moral score.

interface DividingGroup {
  cluster_id: string;
  label: string;
  size: number;
  centroid: string;
}

interface DividingEntity {
  entity_id: number;
  name: string;
  f: number;
  spread: number;
  means: (number | null)[];
  support: number[];
}

interface DividingLines {
  window_start: string | null;
  window_end: string | null;
  groups: DividingGroup[];
  entities: DividingEntity[];
}

const SHOWN = 15;

// Score -> alpha-blended cell background: teal for positive, red for negative,
// stronger with magnitude. Alpha blending keeps ink readable on every cell.
const cellBg = (score: number): string => {
  const alpha = Math.min(Math.abs(score) / 2, 1) * 0.55;
  const rgb = score >= 0 ? '14, 110, 120' : '172, 42, 60'; // accent / villain
  return `rgba(${rgb}, ${alpha})`;
};

const DividingLinesPanel: React.FC = () => {
  const [data, setData] = useState<DividingLines | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    similarityApi
      .getDividingLines({ limit: SHOWN })
      .then((d: DividingLines) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, []);

  if (data && (data.groups.length < 2 || data.entities.length === 0)) return null;

  return (
    <Card>
      <CardHeader
        title="The dividing lines"
        subheader={`What the constellations disagree about — each bloc's mean moral score on the entities that split them sharpest${
          data?.window_start ? ` (${data.window_start} to ${data.window_end})` : ''
        }`}
      />
      <CardContent sx={{ pt: 0 }}>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {!data && !error && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        {data && (
          <>
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small" sx={{ '& td, & th': { borderColor: tokens.border } }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ color: tokens.inkMuted, fontSize: 12 }}>Entity</TableCell>
                    {data.groups.map((g) => (
                      <TableCell key={g.cluster_id} align="center" sx={{ minWidth: 76 }}>
                        <Typography variant="caption" sx={{ color: tokens.ink, fontWeight: 600, display: 'block' }}>
                          {g.label}
                        </Typography>
                        <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', lineHeight: 1.2 }} noWrap>
                          {g.size} papers · {g.centroid}
                        </Typography>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.entities.slice(0, SHOWN).map((e) => (
                    <TableRow key={e.entity_id} hover>
                      <TableCell sx={{ color: tokens.ink, fontSize: 13, whiteSpace: 'nowrap' }}>
                        {e.name}
                      </TableCell>
                      {data.groups.map((g, gi) => {
                        const mean = e.means[gi];
                        return (
                          <TableCell
                            key={g.cluster_id}
                            align="center"
                            title={mean == null
                              ? 'below the 2-source support floor'
                              : `${e.support[gi]} papers`}
                            sx={{
                              ...monoNumber,
                              fontSize: 12,
                              bgcolor: mean == null ? 'transparent' : cellBg(mean),
                              color: mean == null ? tokens.border : tokens.ink,
                            }}
                          >
                            {mean == null ? '—' : `${mean >= 0 ? '+' : ''}${mean.toFixed(2)}`}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
            <Typography variant="caption" sx={{ display: 'block', mt: 1.5, color: tokens.inkMuted }}>
              Groups are the constellations above, numbered the same way (largest first,
              named by their most-connected paper). Rows are ranked by how widely the
              groups' mean readings spread, weighted by how many papers back each mean;
              splits that a noise test can't distinguish from chance are dropped. A "—"
              means fewer than two of that group's papers scored the entity this window.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default DividingLinesPanel;
