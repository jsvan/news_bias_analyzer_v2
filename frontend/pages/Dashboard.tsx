import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Box, 
  Typography, 
  CircularProgress, 
  Container,
  Grid,
  Card, 
  CardContent,
  CardHeader,
  Tabs,
  Tab,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Paper,
  Alert,
  Autocomplete,
  TextField,
  IconButton,
  Tooltip,
  Divider
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoIcon from '@mui/icons-material/Info';
import DownloadIcon from '@mui/icons-material/Download';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';

import { api, entityApi, sourcesApi, statsApi } from '../services/api';
import SentimentChart from '../components/SentimentChart';
import SentimentDistributionChart from '../components/SentimentDistributionChart';
import EntityTrendChart from '../components/EntityTrendChart';
import SourceBiasChart from '../components/SourceBiasChart';
import MultiSourceTrendChart from '../components/MultiSourceTrendChart';
import IntelligenceInsights from '../components/IntelligenceInsights';
import CountryEntityPage from './CountryEntityPage';

// Types
import { 
  Entity, 
  NewsSource, 
  EntitySentimentSummary,
  SentimentDistributions,
  TrendData,
  TrendPoint 
} from '../types';

const Dashboard: React.FC = () => {
  // State for data
  const [entities, setEntities] = useState<Entity[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [highlightedEntities, setHighlightedEntities] = useState<EntitySentimentSummary[]>([]);
  const [distributions, setDistributions] = useState<Record<string, SentimentDistributions>>({});
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [sourceComparisons, setSourceComparisons] = useState<any>({});
  
  // Selected items
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedSources, setSelectedSources] = useState<number[]>([]);
  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(30); // days
  const [selectedTrendEntities, setSelectedTrendEntities] = useState<string[]>([]);
  const [multiEntityTrends, setMultiEntityTrends] = useState<Record<string, any[]>>({});
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [sourcesTrends, setSourcesTrends] = useState<Record<string, any[]>>({});
  
  // Country analysis state
  const [selectedCountry, setSelectedCountry] = useState<string>('USA');
  
  // UI state
  const [currentTab, setCurrentTab] = useState(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshingData, setRefreshingData] = useState<boolean>(false);
  
  // Entity autocomplete state
  const [entitySearchOptions, setEntitySearchOptions] = useState<Entity[]>([]);
  const [entitySearchLoading, setEntitySearchLoading] = useState<boolean>(false);
  const [entitySearchInput, setEntitySearchInput] = useState<string>('');


  // We'll fetch all data directly from the API

  interface TrendPoint {
    date: string;
    power_score: number;
    moral_score: number;
    mention_count: number;
  }

  // Fetch data on component mount
  useEffect(() => {
    fetchInitialData();
  }, []);

  // Fetch initial source trends when entities and selectedEntity are ready
  useEffect(() => {
    if (entities.length > 0 && selectedEntity && selectedCountries.length === 0) {
      fetchSourceTrendsForEntity(selectedEntity, selectedCountries);
    }
  }, [entities, selectedEntity, selectedCountries]);

  const fetchInitialData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch real data from the API
      
      // Fetch news sources
      const sourcesResponse = await api.get('/sources');
      const sourcesData = sourcesResponse.data || [];
      setSources(sourcesData);
      
      // Set some default selected sources if available
      if (sourcesData.length > 0) {
        setSelectedSources(sourcesData.slice(0, Math.min(3, sourcesData.length)).map((s: any) => s.id));
      }
      
      // Fetch entities (sorted by mention count)
      const entitiesResponse = await api.get('/entities?limit=200');
      const entitiesData = entitiesResponse.data || [];
      setEntities(entitiesData);
      
      // Set default selected entity if available
      if (entitiesData.length > 0) {
        setSelectedEntity(entitiesData[0].name);
      }
      
      // Fetch trending entities with sentiment scores
      try {
        const trendingEntitiesResponse = await api.get('/stats/trending_entities');
        setHighlightedEntities(trendingEntitiesResponse.data || []);
      } catch (err) {
        console.warn('Could not fetch trending entities:', err);
        setHighlightedEntities([]);
      }
      
      // Fetch distributions for entities
      const distributionsMap: Record<string, SentimentDistributions> = {};
      
      // Fetch entity distributions for the first entity
      if (entitiesData.length > 0) {
        try {
          const entityDistributionResponse = await entityApi.getEntityDistribution(entitiesData[0].id);
          if (entityDistributionResponse) {
            distributionsMap[entitiesData[0].name] = entityDistributionResponse;
          }
        } catch (err) {
          console.warn(`Could not fetch distribution for ${entitiesData[0].name}:`, err);
        }
      }
      
      setDistributions(distributionsMap);
      
      // Fetch trend data
      try {
        const trendsResponse = await statsApi.getHistoricalSentiment(
          entitiesData.length > 0 ? entitiesData[0].id : 0, 
          { days: selectedTimeRange }
        );
        
        if (trendsResponse && trendsResponse.daily_data) {
          setTrends(trendsResponse.daily_data);
        } else {
          setTrends([]);
        }
      } catch (err) {
        console.warn('Could not fetch trend data:', err);
        setTrends([]);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching data:', error);
      const errorMessage = (error as Error).message;
      
      if (errorMessage.includes('API unavailable')) {
        setError('⚠️ Backend server required for accurate news analysis.\n\nThis system requires real data - no mock data is provided for reliability.\n\nTo use the dashboard:\n• Run locally: `python server/dashboard_api.py`\n• Or set VITE_API_BASE_URL to your hosted API');
      } else {
        setError('Failed to connect to the news analysis API. Please ensure the backend server is running and accessible.');
      }
      setLoading(false);
    }
  };

  const refreshData = async () => {
    setRefreshingData(true);
    
    try {
      // Fetch fresh data from the API
      if (entities.length > 0) {
        // Refresh trending entities
        try {
          const trendingEntitiesResponse = await api.get('/stats/trending_entities');
          setHighlightedEntities(trendingEntitiesResponse.data || []);
        } catch (err) {
          console.warn('Could not refresh trending entities:', err);
        }
        
        // Refresh distribution for selected entity
        if (selectedEntity) {
          try {
            const entityObj = entities.find(e => e.name === selectedEntity);
            if (entityObj) {
              const entityDistributionResponse = await entityApi.getEntityDistribution(entityObj.id);
              if (entityDistributionResponse) {
                setDistributions(prev => ({
                  ...prev,
                  [selectedEntity]: entityDistributionResponse
                }));
              }
            }
          } catch (err) {
            console.warn(`Could not refresh distribution for ${selectedEntity}:`, err);
          }
        }
        
        // Refresh trend data
        try {
          const entityObj = entities.find(e => e.name === selectedEntity);
          if (entityObj) {
            const trendsResponse = await statsApi.getHistoricalSentiment(
              entityObj.id, 
              { days: selectedTimeRange }
            );
            
            if (trendsResponse && trendsResponse.daily_data) {
              setTrends(trendsResponse.daily_data);
            }
          }
        } catch (err) {
          console.warn('Could not refresh trend data:', err);
        }
      }
    } catch (error) {
      console.error('Error refreshing data:', error);
    } finally {
      setRefreshingData(false);
    }
  };

  // Entity search with debouncing
  const searchEntities = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      // For short queries, show popular entities from cache
      setEntitySearchOptions(entities.slice(0, 20));
      return;
    }

    setEntitySearchLoading(true);
    try {
      const searchResults = await entityApi.searchEntities(query, 15);
      setEntitySearchOptions(searchResults);
    } catch (err) {
      console.warn('Entity search failed:', err);
      // Fallback to local filtering
      const filtered = entities.filter(entity => 
        entity.name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 15);
      setEntitySearchOptions(filtered);
    } finally {
      setEntitySearchLoading(false);
    }
  }, [entities]);

  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchEntities(entitySearchInput);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [entitySearchInput, searchEntities]);

  // Initialize entity search options with popular entities
  useEffect(() => {
    if (entities.length > 0 && entitySearchOptions.length === 0) {
      setEntitySearchOptions(entities.slice(0, 20));
    }
  }, [entities, entitySearchOptions.length]);

  const fetchTrendDataForEntities = async (entityNames: string[]) => {
    if (entityNames.length === 0) {
      setMultiEntityTrends({});
      return;
    }

    const newTrends: Record<string, any[]> = {};
    
    for (const entityName of entityNames) {
      try {
        const entityObj = entities.find(e => e.name === entityName);
        if (entityObj) {
          const trendsResponse = await statsApi.getHistoricalSentiment(
            entityObj.id, 
            { days: selectedTimeRange }
          );
          
          if (trendsResponse && trendsResponse.daily_data) {
            newTrends[entityName] = trendsResponse.daily_data;
          }
        }
      } catch (err) {
        console.warn(`Could not fetch trend data for ${entityName}:`, err);
      }
    }
    
    setMultiEntityTrends(newTrends);
  };

  const fetchSourceTrendsForEntity = async (entityName: string, countries: string[] = []) => {
    if (!entityName) {
      setSourcesTrends({});
      return;
    }

    const entityObj = entities.find(e => e.name === entityName);
    if (!entityObj) return;

    try {
      // Use the new source-specific historical sentiment endpoint
      const params: any = { days: selectedTimeRange };
      if (countries.length > 0) {
        params.countries = countries;
      }
      
      const sourceHistoricalResponse = await statsApi.getSourceHistoricalSentiment(entityObj.id, params);
      
      if (sourceHistoricalResponse && sourceHistoricalResponse.sources) {
        const sourceTrends: Record<string, any[]> = {};
        
        // Convert the API response to the format expected by the chart
        Object.entries(sourceHistoricalResponse.sources).forEach(([sourceKey, sourceData]: [string, any]) => {
          if (sourceData.daily_data && sourceData.daily_data.length > 0) {
            sourceTrends[sourceKey] = sourceData.daily_data;
          }
        });
        
        setSourcesTrends(sourceTrends);
        console.log(`Found real trend data for ${Object.keys(sourceTrends).length} sources for ${entityName}`);
        console.log('Countries filter applied:', countries);
        console.log('Available sources:', Object.keys(sourceTrends));
      } else {
        // Fallback to global average if no source-specific data
        const historicalResponse = await statsApi.getHistoricalSentiment(entityObj.id, { days: selectedTimeRange });
        
        if (historicalResponse && historicalResponse.daily_data && historicalResponse.daily_data.length > 0) {
          setSourcesTrends({
            'Global Average (All Sources)': historicalResponse.daily_data
          });
          console.log('No source-specific data found, showing global average');
        } else {
          setSourcesTrends({});
        }
      }
    } catch (err) {
      console.error(`Error fetching source historical sentiment for ${entityName}:`, err);
      
      // Fallback to global data
      try {
        const historicalResponse = await statsApi.getHistoricalSentiment(entityObj.id, { days: selectedTimeRange });
        if (historicalResponse && historicalResponse.daily_data) {
          setSourcesTrends({
            'Global Average (All Sources)': historicalResponse.daily_data
          });
        }
      } catch (fallbackErr) {
        console.error('Fallback to global data also failed:', fallbackErr);
        setSourcesTrends({});
      }
    }
  };

  // Get unique countries from sources
  const getAvailableCountries = () => {
    const countries = [...new Set(sources.map(s => s.country).filter(Boolean))];
    return countries.sort();
  };

  const handleTimeRangeChange = async (event: any) => {
    const newRange = event.target.value as number;
    setSelectedTimeRange(newRange);
    
    // Fetch real trend data for the new time range
    if (selectedEntity) {
      try {
        const entityObj = entities.find(e => e.name === selectedEntity);
        if (entityObj) {
          const trendsResponse = await statsApi.getHistoricalSentiment(
            entityObj.id, 
            { days: newRange }
          );
          
          if (trendsResponse && trendsResponse.daily_data) {
            setTrends(trendsResponse.daily_data);
          } else {
            setTrends([]);
          }
        }
      } catch (err) {
        console.warn(`Could not fetch trend data for time range ${newRange}:`, err);
        setTrends([]);
      }
    }
  };


  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom>
          {error}
        </Typography>
        <Typography>
          Please make sure the API server is running at http://localhost:8000
        </Typography>
        <Button 
          variant="contained" 
          sx={{ mt: 3 }} 
          onClick={fetchInitialData}
        >
          Retry
        </Button>
      </Box>
    );
  }

  // Entities are already sorted by mention count from the API


  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            News Bias Analyzer Dashboard
          </Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Tooltip title="Refresh data">
              <IconButton 
                color="primary" 
                onClick={refreshData}
                disabled={refreshingData}
              >
                {refreshingData ? <CircularProgress size={24} /> : <RefreshIcon />}
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Export data as CSV">
              <IconButton color="primary">
                <DownloadIcon />
              </IconButton>
            </Tooltip>
            
            <Button 
              variant="outlined" 
              startIcon={<CompareArrowsIcon />}
              onClick={() => alert('Comparison feature coming soon!')}
            >
              Compare Sources
            </Button>
          </Box>
        </Box>
        
        <Paper sx={{ mb: 4 }}>
          <Tabs
            value={currentTab}
            onChange={(e, newValue) => setCurrentTab(newValue)}
            variant="fullWidth"
          >
            <Tab label="Entity Analysis" />
            <Tab label="Source Comparison" />
            <Tab label="Temporal Trends" />
            <Tab label="Country Analysis" />
            <Tab label="Statistics & Distributions" />
            <Tab label="Intelligence Insights" />
          </Tabs>
        </Paper>
        
        {/* Filters section - only show for tabs that need them */}
        {currentTab !== 3 && currentTab !== 2 && ( /* Hide filters for Country Analysis and Temporal Trends tabs */
          <Paper sx={{ p: 2, mb: 4 }}>
            <Grid container spacing={3} alignItems="center">
              <Grid item xs={12} sm={6} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel id="time-range-label">Time Range</InputLabel>
                  <Select
                    labelId="time-range-label"
                    id="time-range-select"
                    value={selectedTimeRange}
                    onChange={handleTimeRangeChange}
                  >
                    <MenuItem value={7}>Last 7 days</MenuItem>
                    <MenuItem value={30}>Last 30 days</MenuItem>
                    <MenuItem value={90}>Last 3 months</MenuItem>
                    <MenuItem value={180}>Last 6 months</MenuItem>
                    <MenuItem value={365}>Last year</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={6} md={8}>
                <Autocomplete
                  id="entity-autocomplete"
                  options={entities.map(e => ({ label: `${e.name} (${e.mention_count || 0} mentions)`, value: e.name }))}
                  value={entities.find(e => e.name === selectedEntity) ? { label: `${selectedEntity} (${entities.find(e => e.name === selectedEntity)?.mention_count || 0} mentions)`, value: selectedEntity } : null}
                  onChange={(event, newValue) => {
                    if (newValue) setSelectedEntity(newValue.value);
                  }}
                  renderInput={(params) => (
                    <TextField {...params} label="Select Entity (sorted by mention count)" size="small" fullWidth />
                  )}
                  isOptionEqualToValue={(option, value) => option.value === value?.value}
                />
              </Grid>
            </Grid>
          </Paper>
        )}
        
        {/* Main content based on selected tab */}
        {currentTab === 0 && (
          <Grid container spacing={4}>
            <Grid item xs={12} md={7}>
              <Card>
                <CardHeader 
                  title="Entity Sentiment Analysis" 
                  subheader="Power vs. Moral positioning of key entities"
                  action={
                    <Tooltip title="Entities are positioned based on their average sentiment scores across all analyzed news sources. The quadrants represent different narrative archetypes.">
                      <IconButton>
                        <InfoIcon />
                      </IconButton>
                    </Tooltip>
                  }
                />
                <CardContent>
                  <SentimentChart 
                    data={highlightedEntities}
                    entityTypes={{}}
                    height={500}
                    showLabels={true}
                  />
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={5}>
              <Card>
                <CardHeader 
                  title="Entity Distribution" 
                  subheader={`Sentiment distribution for ${selectedEntity}`}
                />
                <CardContent>
                  {distributions[selectedEntity] ? (
                    <SentimentDistributionChart 
                      distributions={distributions[selectedEntity]}
                      entityName={selectedEntity}
                      height={250}
                    />
                  ) : (
                    <Box sx={{ height: 250, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                      <Typography color="text.secondary">Select an entity to view distribution</Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
              
              <Card sx={{ mt: 3 }}>
                <CardHeader 
                  title="Notable Entities" 
                  subheader="Entities with unusual sentiment patterns"
                />
                <CardContent>
                  <Grid container spacing={2}>
                    {highlightedEntities.slice(0, 6).map(entity => (
                      <Grid item xs={12} sm={6} key={entity.entity}>
                        <Paper 
                          elevation={1} 
                          sx={{ 
                            p: 2, 
                            borderLeft: '4px solid',
                            borderColor: entity.moral_score > 0.5 ? 'success.main' : 
                                        entity.moral_score < -0.5 ? 'error.main' :
                                        'warning.main',
                            cursor: 'pointer',
                            '&:hover': { bgcolor: 'action.hover' }
                          }}
                          onClick={() => setSelectedEntity(entity.entity)}
                        >
                          <Typography variant="subtitle1">{entity.entity}</Typography>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                            <Typography variant="body2" color="text.secondary">
                              Power: {entity.power_score.toFixed(1)}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Moral: {entity.moral_score.toFixed(1)}
                            </Typography>
                          </Box>
                          <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                            {entity.global_percentile}% percentile
                          </Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12}>
              <Card>
                <CardHeader 
                  title="Sentiment Over Time" 
                  subheader={`Tracking ${selectedEntity || 'entity'} sentiment trends`}
                />
                <CardContent>
                  {selectedEntity ? (
                    <Box sx={{ height: 400 }}>
                      <EntityTrendChart 
                        entityName={selectedEntity}
                        data={trends || []}
                        height={400}
                      />
                    </Box>
                  ) : (
                    <Box sx={{ height: 400, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                      <Typography color="text.secondary">Select an entity to view trends</Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}
        
        {currentTab === 1 && (
          <Box>
            <Alert severity="info" sx={{ mb: 3 }}>
              Source comparison functionality is under development. It will allow you to compare how different news sources portray the same entities.
            </Alert>
            
            <Grid container spacing={4}>
              <Grid item xs={12}>
                <Card>
                  <CardHeader 
                    title="Source Bias Comparison" 
                    subheader="Compare sentiment patterns across news sources"
                  />
                  <CardContent>
                    <Box sx={{ height: 500, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                      <Typography variant="body1" color="text.secondary">
                        Source comparison visualization coming soon
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        )}
        
        {currentTab === 2 && (
          <Box>
            <Alert severity="info" sx={{ mb: 3 }}>
              Cross-source analysis reveals how different news outlets portray the same entity, exposing narrative divergences and information sphere dynamics.
            </Alert>
            
            {/* Filters for temporal trends */}
            <Paper sx={{ p: 2, mb: 4 }}>
              <Grid container spacing={3} alignItems="center">
                <Grid item xs={12} sm={4}>
                  <Autocomplete
                    id="entity-for-trends"
                    options={entitySearchOptions.map(e => ({ 
                      label: `${e.name} (${e.mention_count || 0} mentions)`, 
                      value: e.name,
                      id: e.id 
                    }))}
                    value={selectedEntity ? { 
                      label: `${selectedEntity} (${entities.find(e => e.name === selectedEntity)?.mention_count || 0} mentions)`, 
                      value: selectedEntity,
                      id: entities.find(e => e.name === selectedEntity)?.id || 0
                    } : null}
                    onChange={(event, newValue) => {
                      if (newValue) {
                        setSelectedEntity(newValue.value);
                        fetchSourceTrendsForEntity(newValue.value, selectedCountries);
                      }
                    }}
                    onInputChange={(event, newInputValue) => {
                      setEntitySearchInput(newInputValue);
                    }}
                    renderInput={(params) => (
                      <TextField 
                        {...params} 
                        label="Search Entity" 
                        size="small" 
                        fullWidth
                        placeholder="Type to search entities..."
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {entitySearchLoading ? <CircularProgress color="inherit" size={20} /> : null}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                    isOptionEqualToValue={(option, value) => option.value === value?.value}
                    loading={entitySearchLoading}
                    filterOptions={(x) => x} // Disable built-in filtering since we handle it server-side
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <Autocomplete
                    multiple
                    id="country-filter"
                    options={getAvailableCountries()}
                    value={selectedCountries}
                    onChange={(event, newValue) => {
                      setSelectedCountries(newValue);
                      if (selectedEntity) {
                        fetchSourceTrendsForEntity(selectedEntity, newValue);
                      }
                    }}
                    renderInput={(params) => (
                      <TextField {...params} label="Filter by Countries" size="small" fullWidth />
                    )}
                    limitTags={2}
                    disableCloseOnSelect
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel id="trend-time-range-label">Time Range</InputLabel>
                    <Select
                      labelId="trend-time-range-label"
                      value={selectedTimeRange}
                      onChange={(e) => {
                        const newRange = e.target.value as number;
                        setSelectedTimeRange(newRange);
                        if (selectedEntity) {
                          fetchSourceTrendsForEntity(selectedEntity, selectedCountries);
                        }
                      }}
                    >
                      <MenuItem value={7}>Last 7 days</MenuItem>
                      <MenuItem value={30}>Last 30 days</MenuItem>
                      <MenuItem value={90}>Last 3 months</MenuItem>
                      <MenuItem value={180}>Last 6 months</MenuItem>
                      <MenuItem value={365}>Last year</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </Paper>
            
            <Grid container spacing={4}>
              {/* Cross-source comparison chart */}
              <Grid item xs={12}>
                <Card>
                  <CardHeader 
                    title={selectedEntity ? `How Different Sources Portray ${selectedEntity}` : "Cross-Source Sentiment Analysis"}
                    subheader={selectedEntity ? `Compare ${Object.keys(sourcesTrends).length} news sources over ${selectedTimeRange} days` : "Select an entity to compare across news sources"}
                  />
                  <CardContent>
                    {selectedEntity && Object.keys(sourcesTrends).length > 0 ? (
                      <Box sx={{ height: 500 }}>
                        <MultiSourceTrendChart 
                          entityName={selectedEntity}
                          sourcesTrends={sourcesTrends}
                          height={500}
                        />
                      </Box>
                    ) : (
                      <Box sx={{ 
                        height: 500, 
                        display: 'flex', 
                        flexDirection: 'column',
                        justifyContent: 'center', 
                        alignItems: 'center',
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                        border: '1px dashed',
                        borderColor: 'divider'
                      }}>
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          {!selectedEntity ? 'Select an entity to analyze cross-source trends' : 'No source-specific data available'}
                        </Typography>
                        {selectedEntity && (
                          <Typography color="text.secondary">
                            No individual newspaper data found for {selectedEntity} in selected countries
                          </Typography>
                        )}
                        {!selectedEntity && (
                          <Typography color="text.secondary">
                            See how CNN, BBC, RT, and other sources portray the same entity differently
                          </Typography>
                        )}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
              
              {/* Source breakdown and insights */}
              {selectedEntity && Object.keys(sourcesTrends).length > 0 && (
                <Grid item xs={12}>
                  <Card>
                    <CardHeader 
                      title="Source Analysis & Divergence Patterns" 
                      subheader="Identify which sources show unusual sentiment patterns"
                    />
                    <CardContent>
                      <Grid container spacing={3}>
                        {Object.entries(sourcesTrends).map(([sourceName, trends]) => {
                          if (trends.length === 0) return null;
                          
                          const avgPower = trends.reduce((sum, t) => sum + t.power_score, 0) / trends.length;
                          const avgMoral = trends.reduce((sum, t) => sum + t.moral_score, 0) / trends.length;
                          const totalMentions = trends.reduce((sum, t) => sum + t.mention_count, 0);
                          
                          return (
                            <Grid item xs={12} sm={6} md={4} key={sourceName}>
                              <Paper elevation={1} sx={{ p: 2, height: '100%' }}>
                                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
                                  {sourceName}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  Power: {avgPower.toFixed(2)} | Moral: {avgMoral.toFixed(2)}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  {totalMentions} total mentions
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  {trends.length} days with data
                                </Typography>
                                {/* Add sentiment characterization */}
                                <Typography variant="caption" sx={{ 
                                  display: 'block', 
                                  mt: 1, 
                                  fontStyle: 'italic',
                                  color: avgMoral > 0.5 ? 'success.main' : avgMoral < -0.5 ? 'error.main' : 'warning.main'
                                }}>
                                  {avgMoral > 0.5 ? '😊 Generally positive' : 
                                   avgMoral < -0.5 ? '😟 Generally negative' : 
                                   '😐 Mixed/neutral'}
                                </Typography>
                              </Paper>
                            </Grid>
                          );
                        })}
                      </Grid>
                    </CardContent>
                  </Card>
                </Grid>
              )}
            </Grid>
          </Box>
        )}
        
        {currentTab === 3 && (
          <CountryEntityPage
            selectedCountry={selectedCountry}
            selectedTimeRange={selectedTimeRange}
            onCountryChange={setSelectedCountry}
            onTimeRangeChange={setSelectedTimeRange}
          />
        )}

        {currentTab === 4 && (
          <Box>
            <Alert severity="info" sx={{ mb: 3 }}>
              Statistical analysis helps identify unusual entity portrayals and media bias patterns.
            </Alert>
            
            <Grid container spacing={4}>
              <Grid item xs={12}>
                <Card>
                  <CardHeader 
                    title="Statistical Distributions" 
                    subheader="Sentiment distribution analysis"
                  />
                  <CardContent>
                    <Box sx={{ height: 500, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                      <Typography variant="body1" color="text.secondary">
                        Statistical analysis visualization coming soon
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        )}

        {currentTab === 5 && (
          <IntelligenceInsights />
        )}
      </Box>
    </Container>
  );
};

export default Dashboard;