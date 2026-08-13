import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  Grid,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Paper,
  Alert,
  Chip,
} from '@mui/material';

import { statsApi } from '../services/api';
import { useData } from '../context/DataContext';
import NewspaperSpreadPanel from '../components/NewspaperSpreadPanel';
import SalienceAsymmetryPanel from '../components/SalienceAsymmetryPanel';
import TimeRangeSelect, { ALL_TIME } from '../components/TimeRangeSelect';
import { CountryTopEntitiesResponse } from '../types';
import { tokens } from '../theme';

// Countries with tracked sources come from DataContext; this static list only
// covers the first render before sources load.
const FALLBACK_COUNTRIES = [
  'USA', 'UK', 'Canada', 'Australia', 'Germany',
  'France', 'Japan', 'Russia', 'China', 'India',
];

const CountryEntityPage: React.FC = () => {
  const navigate = useNavigate();
  const { availableCountries } = useData();
  // Initial country can be deep-linked via ?country=X (e.g. from the World page).
  const [searchParams] = useSearchParams();
  const [selectedCountry, setSelectedCountry] = useState<string>(searchParams.get('country') || 'USA');
  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(ALL_TIME);

  const [countryData, setCountryData] = useState<CountryTopEntitiesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const countryOptions = availableCountries.length > 0 ? availableCountries : FALLBACK_COUNTRIES;

  useEffect(() => {
    if (!selectedCountry) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    statsApi
      .getCountryTopEntities(selectedCountry, { days: selectedTimeRange, limit: 10 })
      .then((data) => {
        if (!cancelled) setCountryData(data);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err.response?.data?.detail || 'Failed to load country data');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCountry, selectedTimeRange]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 1 }}>
        {selectedCountry}'s information sphere
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3, maxWidth: 720 }}>
        Two comparisons, one country: where its own papers disagree with each other, and what it
        is loud or silent about relative to another sphere.
      </Typography>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="small">
              <InputLabel id="country-label">Country</InputLabel>
              <Select
                labelId="country-label"
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value as string)}
                label="Country"
              >
                {countryOptions.map((country) => (
                  <MenuItem key={country} value={country}>
                    {country}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TimeRangeSelect value={selectedTimeRange} onChange={setSelectedTimeRange} options={[7, 14, 30, 60, 90]} />
          </Grid>
        </Grid>
      </Paper>

      {/* Internal divergence: papers within this country on the same entities */}
      {countryData && countryData.entities.length > 0 ? (
        <NewspaperSpreadPanel country={selectedCountry} entities={countryData.entities} />
      ) : countryData ? (
        <Alert severity="warning">
          No entities found with sufficient data for {selectedCountry} in the selected time period.
          Try increasing the time range or selecting a different country.
        </Alert>
      ) : null}

      {/* Selection bias: what this sphere is loud/silent about vs another */}
      <Box sx={{ mt: 4 }}>
        <SalienceAsymmetryPanel countryA={selectedCountry} countries={countryOptions} />
      </Box>

      {/* The sphere's papers, as doors to their profiles rather than an in-page duplicate */}
      {countryData && countryData.available_newspapers.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: tokens.inkMuted }}>
            Tracked papers in {selectedCountry}:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {countryData.available_newspapers.map((newspaper) => (
              <Chip
                key={newspaper}
                label={newspaper}
                size="small"
                clickable
                onClick={() => navigate(`/sources/${encodeURIComponent(newspaper)}`)}
                sx={{
                  cursor: 'pointer',
                  fontWeight: 500,
                  bgcolor: 'transparent',
                  color: tokens.inkMuted,
                  border: `1px solid ${tokens.border}`,
                  '&:hover': { bgcolor: tokens.surfaceSunken },
                }}
              />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default CountryEntityPage;
