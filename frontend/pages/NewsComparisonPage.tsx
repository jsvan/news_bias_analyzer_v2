import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  CircularProgress, 
  Tabs, 
  Tab, 
  Card, 
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  OutlinedInput,
  SelectChangeEvent
} from '@mui/material';
import api from '../services/api';

// Simple type definitions
interface NewsSource {
  id: number;
  name: string;
  country: string;
  political_leaning: string;
  article_count: number;
}

interface Topic {
  id: number;
  name: string;
  description: string;
  quote_count: number;
}

interface Entity {
  id: number;
  name: string;
  type: string;
  mention_count: number;
}

const NewsComparisonPage: React.FC = () => {
  // State for data
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  
  // Selected items
  const [selectedSources, setSelectedSources] = useState<number[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  
  // Loading states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Tab state
  const [tabValue, setTabValue] = useState(0);

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch sources
        const sourcesResponse = await api.get('/similarity/source_list');
        setSources(sourcesResponse.data);
        
        // Default to selecting first 3 sources
        if (sourcesResponse.data && sourcesResponse.data.length > 0) {
          setSelectedSources(sourcesResponse.data.slice(0, 3).map((s: NewsSource) => s.id));
        }
        
        // Fetch topics
        const topicsResponse = await api.get('/similarity/topic_list');
        setTopics(topicsResponse.data);
        
        // Fetch entities
        const entitiesResponse = await api.get('/similarity/entity_list');
        setEntities(entitiesResponse.data);
        
        // Select first entity if available
        if (entitiesResponse.data && entitiesResponse.data.length > 0) {
          setSelectedEntity(entitiesResponse.data[0].name);
        }
        
        setLoading(false);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to load data. Please ensure the API server is running.');
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);
  
  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };
  
  // Handle source selection
  const handleSourceChange = (event: SelectChangeEvent<typeof selectedSources>) => {
    const value = event.target.value as number[];
    setSelectedSources(value);
  };
  
  // Handle entity selection
  const handleEntityChange = (event: SelectChangeEvent) => {
    setSelectedEntity(event.target.value as string);
  };
  
  // Handle topic selection
  const handleTopicChange = (event: SelectChangeEvent<typeof selectedTopics>) => {
    const value = event.target.value as string[];
    setSelectedTopics(value);
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
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom>
        News Bias Analysis Dashboard
      </Typography>
      
      <Typography variant="body1" paragraph>
        Analyze and compare sentiment patterns across different news sources.
      </Typography>
      
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Source Similarity" />
          <Tab label="Entity Sentiment" />
          <Tab label="Topic Coverage" />
        </Tabs>
      </Box>
      
      {/* Source Selection */}
      <Box sx={{ mb: 4 }}>
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel id="news-sources-label">News Sources</InputLabel>
          <Select
            labelId="news-sources-label"
            multiple
            value={selectedSources}
            onChange={handleSourceChange}
            input={<OutlinedInput label="News Sources" />}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {selected.map((value) => {
                  const source = sources.find(s => s.id === value);
                  return source ? (
                    <Chip key={value} label={source.name} />
                  ) : null;
                })}
              </Box>
            )}
          >
            {sources.map((source) => (
              <MenuItem key={source.id} value={source.id}>
                {source.name} ({source.political_leaning})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        
        {tabValue === 1 && (
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel id="entity-label">Entity</InputLabel>
            <Select
              labelId="entity-label"
              value={selectedEntity}
              onChange={handleEntityChange}
              label="Entity"
            >
              {entities.map((entity) => (
                <MenuItem key={entity.id} value={entity.name}>
                  {entity.name} ({entity.type})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        
        {tabValue === 2 && (
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel id="topics-label">Topics</InputLabel>
            <Select
              labelId="topics-label"
              multiple
              value={selectedTopics}
              onChange={handleTopicChange}
              input={<OutlinedInput label="Topics" />}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selected.map((value) => (
                    <Chip key={value} label={value} />
                  ))}
                </Box>
              )}
            >
              {topics.map((topic) => (
                <MenuItem key={topic.id} value={topic.name}>
                  {topic.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>
      
      {/* Tabs Content */}
      <Box>
        {tabValue === 0 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Source Similarity Visualization
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This visualization shows how different news sources cluster based on sentiment similarity. 
                Sources that are closer together have more similar sentiment patterns.
              </Typography>
              <Box sx={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography>
                  Select sources above to view their sentiment similarity visualization
                </Typography>
              </Box>
            </CardContent>
          </Card>
        )}
        
        {tabValue === 1 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Entity Sentiment Trends
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This visualization shows how sentiment toward {selectedEntity || "selected entity"} varies across different news sources over time.
              </Typography>
              <Box sx={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography>
                  Select an entity and sources above to view sentiment trends
                </Typography>
              </Box>
            </CardContent>
          </Card>
        )}
        
        {tabValue === 2 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Topic Coverage Comparison
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This visualization shows how different news sources cover selected topics over time.
              </Typography>
              <Box sx={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography>
                  Select topics and sources above to view coverage comparison
                </Typography>
              </Box>
            </CardContent>
          </Card>
        )}
      </Box>
    </Box>
  );
};

export default NewsComparisonPage;
