import React, { useState } from 'react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ReferenceLine,
  Label
} from 'recharts';
import { 
  Box, 
  Typography, 
  ToggleButtonGroup, 
  ToggleButton, 
  Paper,
  Tooltip as MuiTooltip,
  Chip,
  Grid,
  FormControlLabel,
  Switch
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { CountryEntityData } from '../types';

interface CountryEntitiesTrendChartProps {
  country: string;
  entities: CountryEntityData[];
  height?: number;
  dimension?: 'power' | 'moral' | 'both';
}

// Color palette for entities (more colors since we'll have many entities)
const ENTITY_COLORS = [
  '#e53e3e', '#3182ce', '#38a169', '#d69e2e', '#805ad5', 
  '#ed8936', '#319795', '#c53030', '#2b6cb0', '#2f855a',
  '#b7791f', '#553c9a', '#c05621', '#2c7a7b', '#9c4221',
  '#e56b6f', '#6a4c93', '#f9844a', '#02c39a', '#f15bb5'
];

const CountryEntitiesTrendChart: React.FC<CountryEntitiesTrendChartProps> = ({
  country,
  entities,
  height = 600,
  dimension = 'moral'
}) => {
  const [selectedDimension, setSelectedDimension] = useState<'both' | 'power' | 'moral'>(dimension);
  const [smoothing, setSmoothing] = useState<boolean>(true);
  const [hiddenEntities, setHiddenEntities] = useState<Set<string>>(new Set());

  // Convert entity data to averaged country-level data
  const processEntityData = () => {
    const entityTrends: Record<string, any[]> = {};
    
    entities.forEach(entity => {
      const dailyAverages: Record<string, {power: number[], moral: number[], mentions: number}> = {};
      
      // Aggregate all newspaper data for this entity by date
      Object.entries(entity.newspapers).forEach(([newspaper, trends]) => {
        trends.forEach(point => {
          if (!dailyAverages[point.date]) {
            dailyAverages[point.date] = { power: [], moral: [], mentions: 0 };
          }
          dailyAverages[point.date].power.push(point.power_score);
          dailyAverages[point.date].moral.push(point.moral_score);
          dailyAverages[point.date].mentions += point.mention_count;
        });
      });
      
      // Calculate country averages for each date
      const avgTrends = Object.entries(dailyAverages).map(([date, data]) => ({
        date,
        power_score: data.power.reduce((sum, score) => sum + score, 0) / data.power.length,
        moral_score: data.moral.reduce((sum, score) => sum + score, 0) / data.moral.length,
        mention_count: data.mentions
      })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
      
      entityTrends[entity.entity_name] = avgTrends;
    });
    
    return entityTrends;
  };

  // Combine all entity trends into a single dataset for the chart
  const combineEntityData = () => {
    const entityTrends = processEntityData();
    const allDates = new Set<string>();
    
    // Collect all unique dates across all entities
    Object.values(entityTrends).forEach(trends => {
      trends.forEach(point => allDates.add(point.date));
    });
    
    const sortedDates = Array.from(allDates).sort();
    
    // Create combined dataset
    return sortedDates.map(date => {
      const dataPoint: any = { date };
      
      Object.entries(entityTrends).forEach(([entityName, trends]) => {
        const point = trends.find(t => t.date === date);
        if (point) {
          dataPoint[`${entityName}_power`] = point.power_score;
          dataPoint[`${entityName}_moral`] = point.moral_score;
          dataPoint[`${entityName}_mentions`] = point.mention_count;
        }
      });
      
      return dataPoint;
    });
  };

  const combinedData = combineEntityData();
  const entityNames = entities.map(e => e.entity_name);
  const hasData = entityNames.length > 0 && combinedData.length > 0;

  // Format date for display
  const formatDate = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  // State for tracking which line is being hovered
  const [hoveredLine, setHoveredLine] = useState<string | null>(null);

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length && hoveredLine) {
      // Find the entry that matches the hovered line
      const hoveredEntry = payload.find((p: any) => 
        p.dataKey && p.dataKey.startsWith(hoveredLine) && p.value !== undefined && p.value !== null
      );
      
      if (!hoveredEntry) return null;
      
      const entityName = hoveredEntry.dataKey.replace(/_power|_moral/, '');
      const dimension = hoveredEntry.dataKey.includes('_power') ? 'Power' : 'Moral';
      const entity = entities.find(e => e.entity_name === entityName);
      
      return (
        <Paper 
          elevation={6} 
          sx={{ 
            p: 2, 
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            border: `2px solid ${hoveredEntry.color}`,
            borderRadius: 2,
            minWidth: 200
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              {entityName}
            </Typography>
            {entity && (
              <Chip 
                label={entity.entity_type} 
                size="small" 
                sx={{ ml: 1, fontSize: '0.7rem' }}
              />
            )}
          </Box>
          
          <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
            {formatDate(label)} • {country} Average
          </Typography>
          
          <Box sx={{ mt: 1 }}>
            <Typography 
              variant="body2" 
              sx={{ 
                color: hoveredEntry.color,
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}
            >
              {dimension}: {hoveredEntry.value.toFixed(2)}
            </Typography>
          </Box>
          
          {entity && (
            <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>
              {entity.mention_count} total mentions
            </Typography>
          )}
        </Paper>
      );
    }
    return null;
  };

  const handleDimensionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDimension: 'both' | 'power' | 'moral' | null
  ) => {
    if (newDimension !== null) {
      setSelectedDimension(newDimension);
    }
  };

  const handleSmoothingChange = (
    event: React.MouseEvent<HTMLElement>,
    newSmoothing: boolean | null
  ) => {
    if (newSmoothing !== null) {
      setSmoothing(newSmoothing);
    }
  };

  // Assign colors to entities
  const getEntityColor = (entityName: string) => {
    const index = entityNames.indexOf(entityName);
    return ENTITY_COLORS[index % ENTITY_COLORS.length];
  };

  // Toggle entity visibility
  const toggleEntityVisibility = (entityName: string) => {
    const newHidden = new Set(hiddenEntities);
    if (newHidden.has(entityName)) {
      newHidden.delete(entityName);
    } else {
      newHidden.add(entityName);
    }
    setHiddenEntities(newHidden);
  };

  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ mr: 1 }}>
            {country} Media Landscape - Top Entities
          </Typography>
          <MuiTooltip title="Each line represents the average sentiment for that entity across all news sources in this country.">
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <ToggleButtonGroup
            size="small"
            value={selectedDimension}
            exclusive
            onChange={handleDimensionChange}
            aria-label="dimension selector"
          >
            <ToggleButton value="both" aria-label="both dimensions">
              Both
            </ToggleButton>
            <ToggleButton value="power" aria-label="power dimension">
              Power
            </ToggleButton>
            <ToggleButton value="moral" aria-label="moral dimension">
              Moral
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            size="small"
            value={smoothing}
            exclusive
            onChange={handleSmoothingChange}
            aria-label="smoothing selector"
          >
            <ToggleButton value={true} aria-label="smoothed line">
              Smooth
            </ToggleButton>
            <ToggleButton value={false} aria-label="exact line">
              Exact
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* Entity legend chips */}
      {hasData && (
        <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {entities.map((entity) => {
            const color = getEntityColor(entity.entity_name);
            const isHidden = hiddenEntities.has(entity.entity_name);
            
            return (
              <Chip 
                key={entity.entity_name} 
                label={`${entity.entity_name} (${entity.mention_count})`} 
                size="small" 
                onClick={() => toggleEntityVisibility(entity.entity_name)}
                sx={{
                  backgroundColor: isHidden ? 'action.hover' : `${color}20`,
                  color: isHidden ? 'text.secondary' : color,
                  borderColor: color,
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  opacity: isHidden ? 0.5 : 1,
                  '&:hover': {
                    backgroundColor: isHidden ? 'action.selected' : `${color}30`,
                  }
                }}
                variant={isHidden ? "outlined" : "filled"}
              />
            );
          })}
        </Box>
      )}

      {!hasData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '80%',
          bgcolor: 'background.paper',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'divider',
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary">
            No entity data available for {country}
          </Typography>
        </Box>
      )}

      {hasData && (
        <ResponsiveContainer width="100%" height="85%">
          <LineChart
            data={combinedData}
            margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
            <XAxis 
              dataKey="date" 
              tickFormatter={formatDate}
              padding={{ left: 20, right: 20 }}
            />
            <YAxis 
              domain={[-2, 2]} 
              tickCount={9} 
            >
              <Label 
                value="Sentiment Score" 
                angle={-90} 
                position="insideLeft" 
                style={{ textAnchor: 'middle' }} 
              />
            </YAxis>
            {/* @ts-ignore */}
            <Tooltip 
              content={<CustomTooltip />} 
              cursor={{ stroke: '#666', strokeWidth: 1, strokeDasharray: '3 3' }}
            />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {/* Render lines for each entity */}
            {entityNames.map((entityName, index) => {
              const color = getEntityColor(entityName);
              const isHidden = hiddenEntities.has(entityName);
              
              if (isHidden) return null;
              
              return (
                <React.Fragment key={entityName}>
                  {(selectedDimension === 'both' || selectedDimension === 'power') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${entityName} (Power)`}
                      dataKey={`${entityName}_power`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="5 5"
                      dot={{ strokeWidth: 2, r: 3, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(entityName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(entityName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                  {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${entityName} (Moral)`}
                      dataKey={`${entityName}_moral`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="0"
                      dot={{ strokeWidth: 2, r: 3, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(entityName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(entityName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
};

export default CountryEntitiesTrendChart;