import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  Grid,
  Card, 
  CardContent,
  CardHeader,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Paper,
  Alert,
  Chip,
  Divider
} from '@mui/material';

import { statsApi } from '../services/api';
import CountryEntitiesTrendChart from '../components/CountryEntitiesTrendChart';
import { CountryTopEntitiesResponse, CountryEntityData, NewspaperTopEntitiesResponse } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const CountryEntityPage: React.FC = () => {
  // Route page: owns its own country/time-range state (previously lifted to Dashboard).
  // Initial country can be deep-linked via ?country=X (e.g. from the World page).
  const [searchParams] = useSearchParams();
  const [selectedCountry, setSelectedCountry] = useState<string>(searchParams.get('country') || 'USA');
  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(30);

  // State for data
  const [countryData, setCountryData] = useState<CountryTopEntitiesResponse | null>(null);
  const [selectedNewspaper, setSelectedNewspaper] = useState<string | null>(null);
  const [newspaperData, setNewspaperData] = useState<NewspaperTopEntitiesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Available countries (based on existing dashboard)
  const availableCountries = [
    'USA', 'UK', 'Canada', 'Australia', 'Germany', 
    'France', 'Japan', 'Russia', 'China', 'India'
  ];

  // Fetch data when country or time range changes
  useEffect(() => {
    if (selectedCountry) {
      fetchCountryData();
    }
  }, [selectedCountry, selectedTimeRange]);

  // Clear newspaper selection when country changes
  useEffect(() => {
    setSelectedNewspaper(null);
    setNewspaperData(null);
  }, [selectedCountry]);

  const fetchCountryData = async () => {
    if (!selectedCountry) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await statsApi.getCountryTopEntities(selectedCountry, {
        days: selectedTimeRange,
        limit: 10
      });
      setCountryData(data);
    } catch (err: any) {
      console.error('Error fetching country data:', err);
      setError(err.response?.data?.detail || 'Failed to load country data');
    } finally {
      setLoading(false);
    }
  };

  const handleCountryChange = (event: any) => {
    setSelectedCountry(event.target.value as string);
  };

  const handleTimeRangeChange = (event: any) => {
    setSelectedTimeRange(event.target.value as number);
  };

  const handleNewspaperSelect = async (newspaperName: string) => {
    console.log('Selecting newspaper:', newspaperName);
    
    if (selectedNewspaper === newspaperName) {
      // Deselect if clicking the same newspaper
      setSelectedNewspaper(null);
      setNewspaperData(null);
      return;
    }

    setSelectedNewspaper(newspaperName);
    setError(null);
    
    try {
      const data = await statsApi.getNewspaperTopEntities(newspaperName, {
        days: selectedTimeRange,
        limit: 10
      });
      setNewspaperData(data);
    } catch (err: any) {
      console.error('Error fetching newspaper data:', err);
      setError(err.response?.data?.detail || 'Failed to load newspaper data');
      setNewspaperData(null);
    }
  };

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

  if (!selectedCountry) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Select a Country to Analyze
        </Typography>
        <Typography color="text.secondary">
          Choose a country to see the most discussed entities and how different newspapers portray them.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 3 }}>
        {selectedNewspaper ? (
          <>Analyzing <strong>{selectedNewspaper}</strong>'s most discussed topics. Click another newspaper to compare or click the selected one to return to country overview.</>
        ) : (
          <>Explore how different newspapers within {selectedCountry} portray the same entities. 
          Click on any newspaper below to see their most discussed topics, or view the overall country sentiment patterns.</>
        )}
      </Alert>
      
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="small">
              <InputLabel id="country-label">Country</InputLabel>
              <Select
                labelId="country-label"
                value={selectedCountry}
                onChange={handleCountryChange}
                label="Country"
              >
                {availableCountries.map((country) => (
                  <MenuItem key={country} value={country}>
                    {country}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="small">
              <InputLabel id="time-range-label">Time Range</InputLabel>
              <Select
                labelId="time-range-label"
                value={selectedTimeRange}
                onChange={handleTimeRangeChange}
                label="Time Range"
              >
                <MenuItem value={7}>Last 7 days</MenuItem>
                <MenuItem value={14}>Last 2 weeks</MenuItem>
                <MenuItem value={30}>Last 30 days</MenuItem>
                <MenuItem value={60}>Last 2 months</MenuItem>
                <MenuItem value={90}>Last 3 months</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      {/* Country Overview */}
      {countryData && (
        <Paper sx={{ p: 3, mb: 4, bgcolor: tokens.surface, border: `1px solid ${tokens.border}` }}>
          <Typography variant="h5" gutterBottom>
            {countryData.country} Media Landscape
          </Typography>

          <Grid container spacing={3}>
            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" sx={{ ...monoNumber, color: tokens.accent }}>
                  {countryData.entities.length}
                </Typography>
                <Typography sx={{ color: tokens.inkMuted }}>
                  Top Entities
                </Typography>
              </Box>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" sx={{ ...monoNumber, color: tokens.ink }}>
                  {countryData.available_newspapers.length}
                </Typography>
                <Typography sx={{ color: tokens.inkMuted }}>
                  Newspapers
                </Typography>
              </Box>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" sx={{ ...monoNumber, color: tokens.ink }}>
                  {countryData.time_period_days}
                </Typography>
                <Typography sx={{ color: tokens.inkMuted }}>
                  Days Analyzed
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3, borderColor: tokens.border }} />

          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            Available Newspapers:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {countryData.available_newspapers.map((newspaper) => {
              const isSelected = selectedNewspaper === newspaper;
              return (
                <Chip
                  key={newspaper}
                  label={newspaper}
                  size="small"
                  clickable
                  onClick={() => handleNewspaperSelect(newspaper)}
                  sx={{
                    cursor: 'pointer',
                    fontWeight: 500,
                    bgcolor: isSelected ? tokens.accent : 'transparent',
                    color: isSelected ? '#FFFFFF' : tokens.inkMuted,
                    border: `1px solid ${isSelected ? tokens.accent : tokens.border}`,
                    '&:hover': {
                      bgcolor: isSelected ? tokens.accentHover : tokens.surfaceSunken,
                    },
                  }}
                />
              );
            })}
          </Box>
        </Paper>
      )}

      {/* Selected Newspaper Analysis */}
      {selectedNewspaper && newspaperData && (
        <Card sx={{ mb: 4 }}>
          <CardHeader 
            title={`${selectedNewspaper} - Most Discussed Topics`}
            subheader={`Top entities covered by ${selectedNewspaper} over the last ${selectedTimeRange} days`}
          />
          <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
            <Box sx={{ columns: { xs: 1, sm: 2, md: 3 }, columnGap: 0 }}>
              {newspaperData.entities.map((entity, index) => (
                <Box
                  key={entity.entity_name}
                  sx={{
                    breakInside: 'avoid',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.25,
                    borderTop: index === 0 ? 'none' : `1px solid ${tokens.border}`,
                    '&:hover': { bgcolor: tokens.surfaceSunken },
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      flexShrink: 0,
                      bgcolor: archetypeColor(entity.avg_power_score, entity.avg_moral_score),
                    }}
                  />
                  <Typography
                    variant="body2"
                    sx={{ flex: 1, minWidth: 0, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  >
                    {entity.entity_name}
                  </Typography>
                  <Chip
                    label={entity.entity_type}
                    size="small"
                    variant="outlined"
                    sx={{ borderColor: tokens.border, color: tokens.inkMuted, flexShrink: 0 }}
                  />
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, flexShrink: 0 }}>
                    P {entity.avg_power_score.toFixed(2)} · M {entity.avg_moral_score.toFixed(2)}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 78, textAlign: 'right', flexShrink: 0 }}
                  >
                    {entity.mention_count} mentions
                  </Typography>
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Main Chart - All Entities on One Graph */}
      {!selectedNewspaper && countryData && countryData.entities.length > 0 ? (
        <Card>
          <CardHeader 
            title={`${selectedCountry} Media Sentiment Overview`}
            subheader={`Sentiment trends for top ${countryData.entities.length} entities averaged across ${countryData.available_newspapers.length} newspapers`}
          />
          <CardContent>
            <CountryEntitiesTrendChart 
              country={selectedCountry}
              entities={countryData.entities}
              height={600}
            />
          </CardContent>
        </Card>
      ) : !selectedNewspaper && countryData ? (
        <Alert severity="warning">
          No entities found with sufficient data for {selectedCountry} in the selected time period.
          Try increasing the time range or selecting a different country.
        </Alert>
      ) : null}

      {/* Entity Summary Table */}
      {!selectedNewspaper && countryData && countryData.entities.length > 0 && (
        <Card sx={{ mt: 4 }}>
          <CardHeader 
            title="Entity Summary"
            subheader="Average sentiment scores and mention counts"
          />
          <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
            <Box sx={{ columns: { xs: 1, sm: 2, md: 3 }, columnGap: 0 }}>
              {countryData.entities.map((entity, index) => (
                <Box
                  key={entity.entity_name}
                  sx={{
                    breakInside: 'avoid',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.25,
                    borderTop: index === 0 ? 'none' : `1px solid ${tokens.border}`,
                    '&:hover': { bgcolor: tokens.surfaceSunken },
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      flexShrink: 0,
                      bgcolor: archetypeColor(entity.avg_power_score, entity.avg_moral_score),
                    }}
                  />
                  <Typography
                    variant="body2"
                    sx={{ flex: 1, minWidth: 0, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  >
                    {entity.entity_name}
                  </Typography>
                  <Chip
                    label={entity.entity_type}
                    size="small"
                    variant="outlined"
                    sx={{ borderColor: tokens.border, color: tokens.inkMuted, flexShrink: 0 }}
                  />
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, flexShrink: 0 }}>
                    P {entity.avg_power_score.toFixed(2)} · M {entity.avg_moral_score.toFixed(2)}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 96, textAlign: 'right', flexShrink: 0 }}
                  >
                    {entity.mention_count} · {Object.keys(entity.newspapers).length}np
                  </Typography>
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default CountryEntityPage;