import React, { useEffect, useMemo, useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
} from '@mui/material';
import { tokens, monoNumber } from '../theme';
import { narrativeApi } from '../services/api';

// Salience asymmetry (server/routers/narrative_endpoints.py::
// get_salience_asymmetry, kernel analyzer/narrative_metrics.py::
// salience_asymmetry): selection bias as its own lens. Two spheres can score
// an entity identically and still diverge enormously in whether they mention
// it AT ALL - what a sphere is loud about vs silent about, distinct from how
// it frames what it does cover.

interface SalienceEntry {
  entity_name: string;
  salience_asymmetry: number;
  mentions_a: number;
  mentions_b: number;
}

interface Props {
  countryA: string;
  countries: string[]; // available comparison countries
}

const SalienceAsymmetryPanel: React.FC<Props> = ({ countryA, countries }) => {
  const otherOptions = useMemo(
    () => countries.filter((c) => c !== countryA),
    [countries, countryA]
  );
  const [countryB, setCountryB] = useState<string>('');
  const [entries, setEntries] = useState<SalienceEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the comparison country valid whenever the page's country changes.
  useEffect(() => {
    if (!otherOptions.includes(countryB)) {
      setCountryB(otherOptions[0] ?? '');
    }
  }, [otherOptions, countryB]);

  useEffect(() => {
    if (!countryA || !countryB) return;
    setLoading(true);
    setError(null);
    narrativeApi
      .getSalienceAsymmetry({ country_a: countryA, country_b: countryB, days: 30, limit: 12 })
      .then((data: SalienceEntry[]) => setEntries(data))
      .catch((err) => {
        setEntries(null);
        setError((err as Error).message);
      })
      .finally(() => setLoading(false));
  }, [countryA, countryB]);

  const maxAbs = useMemo(
    () => Math.max(1, ...(entries ?? []).map((e) => Math.abs(e.salience_asymmetry))),
    [entries]
  );

  return (
    <Card>
      <CardHeader
        title="Loud and silent"
        subheader={`What ${countryA}'s press talks about that ${countryB || '…'}'s doesn't — and vice versa (last 30 days)`}
        action={
          <FormControl size="small" sx={{ minWidth: 140, mt: 1, mr: 1 }}>
            <InputLabel>Compare with</InputLabel>
            <Select
              value={countryB}
              label="Compare with"
              onChange={(e) => setCountryB(e.target.value)}
            >
              {otherOptions.map((c) => (
                <MenuItem key={c} value={c}>
                  {c}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={22} />
          </Box>
        )}
        {error && !loading && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {entries && !loading && entries.length === 0 && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            Not enough overlapping coverage between these two spheres in the window.
          </Typography>
        )}
        {entries && !loading && entries.length > 0 && (
          <>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                px: 0.5,
                pb: 0.5,
              }}
            >
              <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                ← louder in {countryB}
              </Typography>
              <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                louder in {countryA} →
              </Typography>
            </Box>
            {entries.map((e) => {
              const frac = Math.abs(e.salience_asymmetry) / maxAbs;
              const towardA = e.salience_asymmetry > 0;
              return (
                <Box
                  key={e.entity_name}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 120px 1fr',
                    alignItems: 'center',
                    gap: 1,
                    py: 0.6,
                    borderTop: `1px solid ${tokens.border}`,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                    {!towardA && (
                      <Box
                        sx={{
                          width: `${frac * 100}%`,
                          height: 8,
                          bgcolor: tokens.threat,
                          borderRadius: '4px 0 0 4px',
                          opacity: 0.75,
                        }}
                      />
                    )}
                  </Box>
                  <Box sx={{ textAlign: 'center', minWidth: 0 }}>
                    <Typography variant="body2" sx={{ color: tokens.ink }} noWrap>
                      {e.entity_name}
                    </Typography>
                    <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                      {e.mentions_a} · {e.mentions_b}
                    </Typography>
                  </Box>
                  <Box>
                    {towardA && (
                      <Box
                        sx={{
                          width: `${frac * 100}%`,
                          height: 8,
                          bgcolor: tokens.accent,
                          borderRadius: '0 4px 4px 0',
                          opacity: 0.75,
                        }}
                      />
                    )}
                  </Box>
                </Box>
              );
            })}
            <Typography variant="caption" sx={{ display: 'block', mt: 1.5, color: tokens.inkMuted }}>
              Bar length is log-odds of coverage share (mention counts under the name). Silence is
              a choice too — an entity one sphere ignores entirely ranks highest here.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default SalienceAsymmetryPanel;
