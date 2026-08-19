import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Box, Typography } from '@mui/material';
import { tokens, categoricalColor, fontSans } from '../theme';

// One-vs-all: where every source sits on the correlation axis relative to the
// picked one. The nearest/farthest lists show the extremes; this strip shows
// the whole distribution between them - is the picked source broadly in
// agreement with the world, or genuinely contested? Dot size is confidence
// (shared-entity count), color is country, click opens the pair scatter.

echarts.use([ScatterChart, GridComponent, TooltipComponent, MarkLineComponent,
              CanvasRenderer]);

export interface SpectrumRow {
  source_id: number;
  name: string;
  country: string | null;
  score: number;
  common_entities: number;
}

const LANES = 6; // deterministic vertical jitter so dots don't stack

const SourceSpectrumStrip: React.FC<{
  rows: SpectrumRow[];
  countryOrder: string[];
  onPick: (row: SpectrumRow) => void;
}> = ({ rows, countryOrder, onPick }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  const data = useMemo(
    () =>
      rows.map((row, i) => ({
        name: row.name,
        value: [row.score, (i % LANES) + 1],
        row,
        symbolSize: 5 + 6 * Math.min(row.common_entities / 50, 1),
        itemStyle: {
          color: categoricalColor(row.country ?? 'Unknown', countryOrder),
          opacity: 0.85,
        },
      })),
    [rows, countryOrder]
  );

  useEffect(() => {
    if (!data.length || !chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
      chartInstance.current.on('click', (params: any) => {
        if (params.data?.row) pickRef.current(params.data.row);
      });
    }
    const chart = chartInstance.current;

    chart.setOption({
      animation: false,
      grid: { top: 6, right: 12, bottom: 22, left: 12 },
      xAxis: {
        type: 'value',
        min: -1,
        max: 1,
        axisLabel: { fontSize: 9, color: tokens.inkMuted,
                     formatter: (v: number) => (v > 0 ? `+${v}` : `${v}`) },
        splitLine: { lineStyle: { color: tokens.border, type: 'dashed' } },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      yAxis: { type: 'value', min: 0, max: LANES + 1, show: false },
      tooltip: {
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (p: any) =>
          `${p.data.row.name}<br/><span style="color:${tokens.inkMuted};font-size:11px">` +
          `r = ${p.value[0] >= 0 ? '+' : ''}${p.value[0].toFixed(2)} · ` +
          `${p.data.row.common_entities} shared entities · click for detail</span>`,
      },
      series: [{
        type: 'scatter',
        data,
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: tokens.border, width: 1 },
          label: { show: false },
          data: [{ xAxis: 0 }],
        },
        emphasis: { itemStyle: { opacity: 1, borderColor: tokens.ink, borderWidth: 1 } },
      }],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [data]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    []
  );

  if (!data.length) return null;

  return (
    <Box>
      <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
        THE WHOLE SPECTRUM
      </Typography>
      <Box ref={chartRef} sx={{ width: '100%', height: 110 }} />
      <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
        Every comparable source on the correlation axis — dot size is shared coverage,
        color is country, click a dot for the pair detail.
      </Typography>
    </Box>
  );
};

export default SourceSpectrumStrip;
