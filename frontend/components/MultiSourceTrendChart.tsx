import React, { useState, useMemo } from 'react';
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
  Chip
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, categoricalColor, monoNumber } from '../theme';

// Define interfaces
interface TrendPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
}

interface MultiSourceTrendChartProps {
  entityName: string;
  sourcesTrends: Record<string, TrendPoint[]>;
  height?: number;
  dimension?: 'power' | 'moral' | 'both';
  // Controlled mode: a page-wide toggle owns the dimension; the internal
  // toggle is not rendered. `dimension` alone stays the uncontrolled default.
  controlledDimension?: 'power' | 'moral' | 'both';
  // Explicit per-series colors (e.g. subject = accent, baseline = gray).
  // Series without an entry keep the country-categorical assignment.
  colors?: Record<string, string>;
}

// Line style patterns: Power lines are always dashed, Moral lines are always solid

const MultiSourceTrendChart: React.FC<MultiSourceTrendChartProps> = ({
  entityName,
  sourcesTrends,
  height = 400,
  dimension = 'moral',
  controlledDimension,
  colors
}) => {
  const [internalDimension, setInternalDimension] = useState<'both' | 'power' | 'moral'>(dimension);
  const selectedDimension = controlledDimension ?? internalDimension;
  // Sources hidden via their legend chip. The legend is the control, not a
  // separate static block restating it.
  const [hiddenSources, setHiddenSources] = useState<Set<string>>(new Set());

  // Get all source names first
  const allSourceNames = Object.keys(sourcesTrends);

  // Combine all source data into a single dataset for the chart
  const combineSourceData = () => {
    const allDates = new Set<string>();

    // Collect all unique dates across all sources
    Object.values(sourcesTrends).forEach(trends => {
      trends.forEach(point => allDates.add(point.date));
    });

    const sortedDates = Array.from(allDates).sort();

    // Create combined dataset
    return sortedDates.map(date => {
      const dataPoint: any = { date };

      Object.entries(sourcesTrends).forEach(([sourceName, trends]) => {
        const point = trends.find(t => t.date === date);
        if (point) {
          dataPoint[`${sourceName}_power`] = (typeof point.power_score === 'number' && !isNaN(point.power_score)) ? point.power_score : null;
          dataPoint[`${sourceName}_moral`] = (typeof point.moral_score === 'number' && !isNaN(point.moral_score)) ? point.moral_score : null;
          dataPoint[`${sourceName}_mentions`] = point.mention_count;
        }
      });

      return dataPoint;
    });
  };

  const combinedData = useMemo(() => combineSourceData(), [sourcesTrends]);

  // Use all source names - don't filter them out
  const sourceNames = allSourceNames;
  const visibleSourceNames = sourceNames.filter((name) => !hiddenSources.has(name));

  const toggleSource = (name: string) => {
    setHiddenSources((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Check if we have valid data for rendering
  const hasValidData = useMemo(() => {
    if (sourceNames.length === 0 || combinedData.length === 0) return false;

    // Check if there's at least one non-null value in the data
    const hasValidValues = combinedData.some(dataPoint =>
      sourceNames.some(sourceName => {
        const powerValue = dataPoint[`${sourceName}_power`];
        const moralValue = dataPoint[`${sourceName}_moral`];
        return (typeof powerValue === 'number' && !isNaN(powerValue)) ||
               (typeof moralValue === 'number' && !isNaN(moralValue));
      })
    );

    return hasValidValues;
  }, [sourceNames, combinedData]);

  const hasData = hasValidData;



  // Format date for display
  // Include the year when the series crosses a year boundary — sparse all-time
  // ticks without it read as out of order.
  const formatDate = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
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

      const sourceName = hoveredEntry.dataKey.replace(/_power|_moral/, '');
      const dimension = hoveredEntry.dataKey.includes('_power') ? 'Power' : 'Moral';
      const country = getCountryFromSource(sourceName);
      // Country's base categorical color (no per-source alpha suffix) — safe to
      // alpha-suffix again below for the chip background.
      const countryBaseColor = categoricalColor(country, countryOrder);

      // Determine line style based on dimension
      const isDashed = dimension === 'Power';

      return (
        <Paper
          elevation={6}
          sx={{
            p: 2,
            bgcolor: tokens.surface,
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
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: tokens.ink }}>
              {sourceName}
            </Typography>
          </Box>

          <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
            {formatDate(label)}
          </Typography>

          <Box sx={{ mt: 1 }}>
            <Typography
              variant="body2"
              sx={{
                ...monoNumber,
                color: hoveredEntry.color,
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}
            >
              {dimension}: {
                typeof hoveredEntry.value === 'number' && !isNaN(hoveredEntry.value)
                  ? hoveredEntry.value.toFixed(2)
                  : 'No data'
              }
            </Typography>
          </Box>

          <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label={country}
              size="small"
              sx={{
                backgroundColor: `${countryBaseColor}20`,
                color: countryBaseColor,
                fontWeight: 'bold',
                fontSize: '0.7rem'
              }}
            />
            <Chip
              label={isDashed ? "dashed" : "solid"}
              size="small"
              variant="outlined"
              sx={{ fontSize: '0.7rem', height: 20, borderColor: tokens.border, color: tokens.inkMuted }}
            />
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
      setInternalDimension(newDimension);
    }
  };


  // Get country from source name (handles both "Source (Country)" and "Country" formats)
  const getCountryFromSource = (sourceName: string) => {
    // First try to extract from parentheses format "Source (Country)"
    const match = sourceName.match(/\(([^)]+)\)$/);
    if (match) {
      return match[1];
    }

    // No parenthetical country given — treat the bare source name as its own
    // grouping key. (Previously this checked membership in a hardcoded country
    // list; that list is gone along with the fixed color map, see below.)
    return sourceName;
  };

  // Group sources by country for better visualization
  const sourcesByCountry = sourceNames.reduce((acc, sourceName) => {
    const country = getCountryFromSource(sourceName);
    if (!acc[country]) acc[country] = [];
    acc[country].push(sourceName);
    return acc;
  }, {} as Record<string, string[]>);

  // Countries in first-appearance order, used to assign stable categorical colors —
  // replaces the old fixed country -> color table (USA=red/UK=blue read as a
  // partisan "sides" mapping, which the design system bans).
  const countryOrder = Object.keys(sourcesByCountry);

  // Same categorical hue per country, stepping opacity per source within it.
  // Computed (not a fixed 4-entry list) so the 5th source in a country doesn't
  // silently recycle the 1st source's exact color. An explicit `colors` entry
  // wins outright — comparison pages assign roles, not countries.
  const getSourceColor = (sourceName: string) => {
    if (colors?.[sourceName]) return colors[sourceName];
    const country = getCountryFromSource(sourceName);
    const baseColor = categoricalColor(country, countryOrder);
    const sourceIndexInCountry = sourcesByCountry[country].indexOf(sourceName);
    const alpha = Math.max(0x55, 0xff - sourceIndexInCountry * 0x2a);
    return `${baseColor}${alpha.toString(16).padStart(2, '0')}`;
  };


  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            {entityName} - Cross-Source Sentiment
          </Typography>
          <MuiTooltip title="Compare how different news sources portray the same entity over time. Each line represents a different newspaper's sentiment. Power lines are dashed, Moral lines solid; click a source chip below to hide or show it."
          >
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        {controlledDimension == null && (
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
        )}
      </Box>

      {/* The legend IS the control: one chip per source, colored like its line,
          click to hide/show. Grouped visually by shared country hue. */}
      {hasData && (
        <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
          {sourceNames.map((sourceName) => {
            const color = getSourceColor(sourceName);
            const hidden = hiddenSources.has(sourceName);
            return (
              <Chip
                key={sourceName}
                label={sourceName}
                size="small"
                onClick={() => toggleSource(sourceName)}
                variant={hidden ? 'outlined' : 'filled'}
                sx={{
                  backgroundColor: hidden ? 'transparent' : `${color}`,
                  color: hidden ? tokens.inkMuted : '#fff',
                  borderColor: color,
                  textDecoration: hidden ? 'line-through' : 'none',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              />
            );
          })}
          <Typography variant="caption" sx={{ color: tokens.inkMuted, ml: 0.5 }}>
            solid = Moral · dashed = Power · click to hide
          </Typography>
        </Box>
      )}

      {!hasData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '80%',
          bgcolor: tokens.surface,
          borderRadius: 1,
          border: `1px dashed ${tokens.border}`,
          p: 3
        }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
            No source-specific trend data available for {entityName}
          </Typography>
        </Box>
      )}

      {hasData && (
        <ResponsiveContainer width="100%" height="85%">
          <LineChart
            key={selectedDimension}
            data={combinedData}
            margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} opacity={0.6} />
            <XAxis
              dataKey="date"
              minTickGap={32}
              tickFormatter={formatDate}
              padding={{ left: 20, right: 20 }}
              stroke={tokens.border}
              tick={{ fill: tokens.inkMuted, fontSize: 11 }}
            />
            <YAxis
              domain={[-2, 2]}
              tickCount={9}
              stroke={tokens.border}
              tick={{ fill: tokens.inkMuted, fontSize: 11 }}
            >
              <Label
                value="Sentiment Score"
                angle={-90}
                position="insideLeft"
                style={{ textAnchor: 'middle', fill: tokens.inkMuted }}
              />
            </YAxis>
            {/* No allowEscapeViewBox: recharts then clamps the tooltip inside the
                plot, so points near the right/bottom edge can't push it off-page. */}
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ stroke: tokens.inkMuted, strokeWidth: 1, strokeDasharray: '3 3' }}
              animationDuration={0}
              animationEasing="linear"
            />
            <ReferenceLine y={0} stroke={tokens.inkMuted} strokeDasharray="3 3" />

            {/* Render lines for each visible source */}
            {visibleSourceNames.map((sourceName) => {
              const color = getSourceColor(sourceName);

              return (
                <React.Fragment key={sourceName}>
                  {(selectedDimension === 'both' || selectedDimension === 'power') && (
                    <Line
                      type="monotone"
                      name={`${sourceName} (Power)`}
                      dataKey={`${sourceName}_power`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="5 5"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{
                        r: 6,
                        strokeWidth: 2,
                        fill: color,
                        onMouseEnter: () => setHoveredLine(sourceName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(sourceName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                  {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                    <Line
                      type="monotone"
                      name={`${sourceName} (Moral)`}
                      dataKey={`${sourceName}_moral`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="0"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{
                        r: 6,
                        strokeWidth: 2,
                        fill: color,
                        onMouseEnter: () => setHoveredLine(sourceName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(sourceName)}
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

export default MultiSourceTrendChart;
