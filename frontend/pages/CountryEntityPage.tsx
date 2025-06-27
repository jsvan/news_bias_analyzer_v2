import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  CircularProgress, 
  Container,
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
import { CountryTopEntitiesResponse, CountryEntityData } from '../types';

interface CountryEntityPageProps {
  selectedCountry: string;
  selectedTimeRange: number;
  onCountryChange: (country: string) => void;
  onTimeRangeChange: (days: number) => void;
}

const CountryEntityPage: React.FC<CountryEntityPageProps> = ({
  selectedCountry,
  selectedTimeRange,
  onCountryChange,
  onTimeRangeChange
}) => {
  // State for data
  const [countryData, setCountryData] = useState<CountryTopEntitiesResponse | null>(null);
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
    const newCountry = event.target.value as string;
    onCountryChange(newCountry);
  };

  const handleTimeRangeChange = (event: any) => {
    const newRange = event.target.value as number;
    onTimeRangeChange(newRange);
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
        Explore how different newspapers within {selectedCountry} portray the same entities. 
        Each chart shows sentiment flows across multiple newspapers, revealing narrative divergences 
        within the country's media landscape.
      </Alert>
      
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 4 }}>
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
        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h5" gutterBottom>
            {countryData.country} Media Landscape
          </Typography>
          
          <Grid container spacing={3}>
            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" color="primary">
                  {countryData.entities.length}
                </Typography>
                <Typography color="text.secondary">
                  Top Entities
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" color="secondary">
                  {countryData.available_newspapers.length}
                </Typography>
                <Typography color="text.secondary">
                  Newspapers
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h3" color="success.main">
                  {countryData.time_period_days}
                </Typography>
                <Typography color="text.secondary">
                  Days Analyzed
                </Typography>
              </Box>
            </Grid>
          </Grid>
          
          <Divider sx={{ my: 3 }} />
          
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
            Available Newspapers:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {countryData.available_newspapers.map((newspaper) => (
              <Chip 
                key={newspaper} 
                label={newspaper} 
                size="small" 
                variant="outlined"
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* Main Chart - All Entities on One Graph */}
      {countryData && countryData.entities.length > 0 ? (
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
      ) : countryData ? (
        <Alert severity="warning">
          No entities found with sufficient data for {selectedCountry} in the selected time period.
          Try increasing the time range or selecting a different country.
        </Alert>
      ) : null}

      {/* Entity Summary Table */}
      {countryData && countryData.entities.length > 0 && (
        <Card sx={{ mt: 4 }}>
          <CardHeader 
            title="Entity Summary"
            subheader="Average sentiment scores and mention counts"
          />
          <CardContent>
            <Grid container spacing={2}>
              {countryData.entities.map((entity, index) => (
                <Grid item xs={12} sm={6} md={4} key={entity.entity_name}>
                  <Paper 
                    elevation={1} 
                    sx={{ 
                      p: 2, 
                      borderLeft: '4px solid',
                      borderColor: entity.avg_moral_score > 0.5 ? 'success.main' : 
                                  entity.avg_moral_score < -0.5 ? 'error.main' :
                                  'warning.main'
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                        {entity.entity_name}
                      </Typography>
                      <Chip 
                        label={entity.entity_type} 
                        size="small" 
                        variant="outlined"
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      Power: {entity.avg_power_score.toFixed(2)} | 
                      Moral: {entity.avg_moral_score.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {entity.mention_count} mentions across {Object.keys(entity.newspapers).length} newspapers
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default CountryEntityPage;