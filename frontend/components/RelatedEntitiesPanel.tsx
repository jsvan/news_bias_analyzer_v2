import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Box, Typography, IconButton, Tooltip, Chip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, monoNumber } from '../theme';
import { embeddingsApi } from '../services/api';

interface RelatedEntity {
  entity_id: number;
  entity_name: string;
  similarity: number;
}

type VectorKind = 'cooccurrence' | 'sentiment';

const VECTOR_LABEL: Record<VectorKind, string> = {
  cooccurrence: 'By topic',
  sentiment: 'By tone',
};

const VECTOR_HELP: Record<VectorKind, string> = {
  cooccurrence: 'Entities that get mentioned in the same articles most often - a topical/associative signal learned from co-occurrence, not asserted.',
  sentiment: 'Entities that get talked about the same way, by the same sources, in the same weeks - a rhetorical signal, distinct from topical co-occurrence.',
};

// "Related entities" - analyzer/entity_embeddings.py's learned relatedness (PPMI +
// TruncatedSVD co-occurrence, and a separate sentiment-profile SVD), served via
// server/routers/embeddings_endpoints.py. Deliberately no hand-curated hierarchy: this
// answers "The West -> USA -> White House -> Trump"-style containment questions from
// what the corpus itself contains, not an asserted taxonomy.
const RelatedEntitiesPanel: React.FC<{ entityId: number }> = ({ entityId }) => {
  const navigate = useNavigate();
  const [vector, setVector] = useState<VectorKind>('cooccurrence');
  const [neighbors, setNeighbors] = useState<RelatedEntity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNeighbors(null);
    setError(null);
    embeddingsApi.getRelated(entityId, { vector, limit: 10 })
      .then((data) => setNeighbors(data.neighbors))
      .catch((err) => setError((err as Error).message));
  }, [entityId, vector]);

  return (
    <Card>
      <CardHeader
        title="Related entities"
        subheader="Learned from the corpus, not asserted"
        action={
          <Tooltip title={VECTOR_HELP[vector]}>
            <IconButton>
              <InfoIcon />
            </IconButton>
          </Tooltip>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
          {(Object.keys(VECTOR_LABEL) as VectorKind[]).map((v) => (
            <Chip
              key={v}
              label={VECTOR_LABEL[v]}
              size="small"
              onClick={() => setVector(v)}
              variant={vector === v ? 'filled' : 'outlined'}
              sx={{
                bgcolor: vector === v ? tokens.accent : 'transparent',
                color: vector === v ? '#fff' : tokens.inkMuted,
                borderColor: tokens.accent,
              }}
            />
          ))}
        </Box>
      </CardContent>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
        {error && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>{error}</Typography>
          </Box>
        )}
        {!error && neighbors === null && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>Loading…</Typography>
          </Box>
        )}
        {!error && neighbors?.length === 0 && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              Not enough mention volume yet for this entity to have a computed relatedness vector.
            </Typography>
          </Box>
        )}
        {neighbors?.map((n, i) => (
          <Box
            key={n.entity_id}
            onClick={() => navigate(`/entities/${n.entity_id}`)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              px: 2,
              py: 1.25,
              cursor: 'pointer',
              borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
              '&:hover': { bgcolor: tokens.surfaceSunken },
            }}
          >
            <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
              {n.entity_name}
            </Typography>
            <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
              {n.similarity.toFixed(3)}
            </Typography>
          </Box>
        ))}
      </CardContent>
    </Card>
  );
};

export default RelatedEntitiesPanel;
