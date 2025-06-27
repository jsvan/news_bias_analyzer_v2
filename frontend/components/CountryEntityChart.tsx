import React, { useState } from 'react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
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

// Define interfaces
interface TrendPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
}

interface CountryEntityChartProps {
  entityName: string;
  newspapers: Record<string, TrendPoint[]>; // newspaper_name -> daily_data
  height?: number;
  dimension?: 'power' | 'moral' | 'both';
}

// Color palette for newspapers (since they're all from same country, use varied colors)
const NEWSPAPER_COLORS = [
  '#e53e3e', '#3182ce', '#38a169', '#d69e2e', '#805ad5', 
  '#ed8936', '#319795', '#c53030', '#2b6cb0', '#2f855a',
  '#b7791f', '#553c9a', '#c05621', '#2c7a7b', '#9c4221'
];

const CountryEntityChart: React.FC<CountryEntityChartProps> = ({
  entityName,
  newspapers,
  height = 400,
  dimension = 'moral'
}) => {
  const [selectedDimension, setSelectedDimension] = useState<'both' | 'power' | 'moral'>(dimension);
  const [smoothing, setSmoothing] = useState<boolean>(true);
  const [showAllLines, setShowAllLines] = useState<boolean>(true);
  const [hiddenNewspapers, setHiddenNewspapers] = useState<Set<string>>(new Set());

  // Combine all newspaper data into a single dataset for the chart
  const combineNewspaperData = () => {
    const allDates = new Set<string>();
    
    // Collect all unique dates across all newspapers
    Object.values(newspapers).forEach(trends => {
      trends.forEach(point => allDates.add(point.date));
    });
    
    const sortedDates = Array.from(allDates).sort();
    
    // Create combined dataset
    return sortedDates.map(date => {
      const dataPoint: any = { date };
      
      Object.entries(newspapers).forEach(([newspaperName, trends]) => {
        const point = trends.find(t => t.date === date);
        if (point) {
          dataPoint[`${newspaperName}_power`] = point.power_score;
          dataPoint[`${newspaperName}_moral`] = point.moral_score;
          dataPoint[`${newspaperName}_mentions`] = point.mention_count;
        }
      });
      
      return dataPoint;
    });
  };

  const combinedData = combineNewspaperData();
  const newspaperNames = Object.keys(newspapers);
  const hasData = newspaperNames.length > 0 && combinedData.length > 0;

  // Format date for display
  const formatDate = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  // State for tracking which line is being hovered
  const [hoveredLine, setHoveredLine] = useState<string | null>(null);

  // Custom tooltip that only shows the hovered line
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length && hoveredLine) {
      // Find the entry that matches the hovered line
      const hoveredEntry = payload.find((p: any) => 
        p.dataKey && p.dataKey.startsWith(hoveredLine) && p.value !== undefined && p.value !== null
      );
      
      if (!hoveredEntry) return null;
      
      const newspaperName = hoveredEntry.dataKey.replace(/_power|_moral/, '');
      const dimension = hoveredEntry.dataKey.includes('_power') ? 'Power' : 'Moral';
      
      // Determine line style based on dimension
      const isDashed = dimension === 'Power';
      
      return (
        <Paper 
          elevation={6} 
          sx={{ 
            p: 2, 
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            border: `2px solid ${hoveredEntry.color}`,
            borderRadius: 2,
            minWidth: 180
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Box 
              sx={{ 
                width: 20, 
                height: 3, 
                bgcolor: hoveredEntry.color,
                mr: 1,
                borderRadius: 1,
                ...(isDashed && {
                  background: `linear-gradient(to right, ${hoveredEntry.color} 60%, transparent 60%)`,
                  backgroundSize: '8px 3px',
                  backgroundRepeat: 'repeat-x'
                })
              }} 
            />
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              {newspaperName}
            </Typography>
          </Box>
          
          <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
            {formatDate(label)}
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

  // Assign colors to newspapers
  const getNewspaperColor = (newspaperName: string) => {
    const index = newspaperNames.indexOf(newspaperName);
    return NEWSPAPER_COLORS[index % NEWSPAPER_COLORS.length];
  };

  // Toggle newspaper visibility
  const toggleNewspaperVisibility = (newspaperName: string) => {
    const newHidden = new Set(hiddenNewspapers);
    if (newHidden.has(newspaperName)) {
      newHidden.delete(newspaperName);
    } else {
      newHidden.add(newspaperName);
    }
    setHiddenNewspapers(newHidden);
  };

  const toggleAllNewspapers = () => {
    if (showAllLines) {
      // Hide all but the first 3 newspapers to reduce clutter
      const toHide = new Set(newspaperNames.slice(3));
      setHiddenNewspapers(toHide);
    } else {
      // Show all newspapers
      setHiddenNewspapers(new Set());
    }
    setShowAllLines(!showAllLines);
  };

  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            {entityName} - Newspaper Sentiment Comparison
          </Typography>
          <MuiTooltip title="Compare how different newspapers within the same country portray this entity over time.">
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={showAllLines}
                onChange={toggleAllNewspapers}
              />
            }
            label="Show All"
            sx={{ mr: 1 }}
          />
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

      {/* Newspaper summary chips */}
      {hasData && (
        <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {newspaperNames.map((newspaperName) => {
            const color = getNewspaperColor(newspaperName);
            const isHidden = hiddenNewspapers.has(newspaperName);
            const mentionCount = newspapers[newspaperName]?.reduce((sum, point) => sum + point.mention_count, 0) || 0;
            
            return (
              <Chip 
                key={newspaperName} 
                label={`${newspaperName} (${mentionCount})`} 
                size="small" 
                onClick={() => toggleNewspaperVisibility(newspaperName)}
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
            No newspaper data available for {entityName}
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
              allowEscapeViewBox={{ x: true, y: true }}
              position={{ x: 'auto', y: 'auto' }}
              animationDuration={0}
              animationEasing="linear"
            />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {/* Render lines for each newspaper */}
            {newspaperNames.map((newspaperName, index) => {
              const color = getNewspaperColor(newspaperName);
              const isHidden = hiddenNewspapers.has(newspaperName);
              
              if (isHidden) return null;
              
              return (
                <React.Fragment key={newspaperName}>
                  {(selectedDimension === 'both' || selectedDimension === 'power') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${newspaperName} (Power)`}
                      dataKey={`${newspaperName}_power`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="5 5"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(newspaperName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(newspaperName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                  {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${newspaperName} (Moral)`}
                      dataKey={`${newspaperName}_moral`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="0"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(newspaperName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(newspaperName)}
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

export default CountryEntityChart;