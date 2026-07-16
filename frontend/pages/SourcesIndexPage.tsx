import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardHeader,
  CardContent,
  Paper,
  Grid,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { NewsSource } from '../types';
import { tokens, monoNumber } from '../theme';

const SourcesIndexPage: React.FC = () => {
  const { sources, availableCountries } = useData();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [country, setCountry] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sources.filter((s) => {
      if (country && s.country !== country) return false;
      if (q && !s.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [sources, query, country]);

  const groups = useMemo(() => {
    const byCountry = new Map<string, NewsSource[]>();
    for (const s of filtered) {
      if (!byCountry.has(s.country)) byCountry.set(s.country, []);
      byCountry.get(s.country)!.push(s);
    }
    return [...byCountry.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  return (
    <Box>
      <Typography
        component="h2"
        sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 3 }}
      >
        News Sources
      </Typography>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={8}>
            <TextField
              label="Filter by name"
              size="small"
              fullWidth
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormControl fullWidth size="small">
              <InputLabel id="country-filter-label">Country</InputLabel>
              <Select
                labelId="country-filter-label"
                value={country}
                label="Country"
                onChange={(e) => setCountry(e.target.value as string)}
              >
                <MenuItem value="">All countries</MenuItem>
                {availableCountries.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      <Card>
        <CardHeader title="Browse all sources" subheader={`${filtered.length} of ${sources.length} tracked sources`} />
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          {groups.length === 0 && (
            <Box sx={{ px: 2, py: 3 }}>
              <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                No sources match this filter.
              </Typography>
            </Box>
          )}
          {groups.map(([groupCountry, list], gi) => (
            <Box key={groupCountry}>
              <Box
                sx={{
                  px: 2,
                  py: 1,
                  bgcolor: tokens.surfaceSunken,
                  borderTop: gi === 0 ? 'none' : `1px solid ${tokens.border}`,
                }}
              >
                <Typography variant="subtitle2" sx={{ color: tokens.inkMuted }}>
                  {groupCountry} &middot; {list.length}
                </Typography>
              </Box>
              {list.map((source) => (
                <Box
                  key={source.id}
                  onClick={() => navigate(`/sources/${encodeURIComponent(source.name)}`)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1,
                    cursor: 'pointer',
                    borderTop: `1px solid ${tokens.border}`,
                    '&:hover': { bgcolor: tokens.surfaceSunken },
                  }}
                >
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {source.name}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                    {source.language}
                  </Typography>
                </Box>
              ))}
            </Box>
          ))}
        </CardContent>
      </Card>
    </Box>
  );
};

export default SourcesIndexPage;
