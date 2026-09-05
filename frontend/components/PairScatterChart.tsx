import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';
import { Box } from '@mui/material';
import { tokens, fontSans } from '../theme';

// The shared-entity scatter behind a similarity number: every entity both
// sources scored in the window, source A's reading on x against source B's on
// y. Points on the diagonal are read identically; the labeled off-diagonal
// outliers are where the two part ways — "they agree on everything except
// Israel and NATO". Extracted from the old PairScatterDialog so the pair PAGE
// (a URL a journalist can send) and any future embed draw the same chart.

echarts.use([ScatterChart, GridComponent, TooltipComponent, MarkLineComponent,
              LabelLayout, CanvasRenderer]);

export interface PairChartEntity {
  entity_id: number;
  name: string;
  score_a: number;
  score_b: number;
  n_a: number;
  n_b: number;
}

// Label only the sharpest disagreements; the rest stay hover-only.
const LABELED_OUTLIERS = 12;

const PairScatterChart: React.FC<{
  aName: string;
  bName: string;
  entities: PairChartEntity[];
  height?: number;
  onPointClick?: (entityId: number) => void;
}> = ({ aName, bName, entities, height = 440, onPointClick }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onPointClick);
  clickRef.current = onPointClick;

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
      chartInstance.current.on('click', (p: any) => {
        if (p.data?.entity_id != null) clickRef.current?.(p.data.entity_id);
      });
    }
    const chart = chartInstance.current;

    const scores = entities.flatMap((e) => [e.score_a, e.score_b]);
    const lo = Math.min(-0.5, ...scores) - 0.15;
    const hi = Math.max(0.5, ...scores) + 0.15;
    const byGap = [...entities].sort(
      (x, y) => Math.abs(y.score_a - y.score_b) - Math.abs(x.score_a - x.score_b));
    const labeled = new Set(byGap.slice(0, LABELED_OUTLIERS).map((e) => e.entity_id));

    const axis = (name: string) => ({
      type: 'value' as const,
      min: lo,
      max: hi,
      name,
      nameLocation: 'middle' as const,
      nameGap: 22,
      nameTextStyle: { fontSize: 11, color: tokens.inkMuted, fontFamily: fontSans },
      axisLabel: { fontSize: 9, color: tokens.inkMuted },
      splitLine: { lineStyle: { color: tokens.border, type: 'dashed' as const } },
    });

    chart.setOption({
      animation: false,
      grid: { top: 14, right: 24, bottom: 40, left: 44 },
      xAxis: axis(`${aName} score`),
      yAxis: axis(`${bName} score`),
      tooltip: {
        trigger: 'item',
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (p: any) =>
          `${p.data.name}<br/><span style="color:${tokens.inkMuted};font-size:11px">` +
          `${aName}: ${p.value[0].toFixed(2)} (${p.data.n_a}×) · ` +
          `${bName}: ${p.value[1].toFixed(2)} (${p.data.n_b}×)</span>`,
      },
      series: [{
        type: 'scatter',
        data: entities.map((e) => ({
          name: e.name,
          entity_id: e.entity_id,
          value: [e.score_a, e.score_b],
          n_a: e.n_a,
          n_b: e.n_b,
          symbolSize: 4 + 2.5 * Math.sqrt(Math.min(e.n_a, e.n_b)),
          label: {
            show: labeled.has(e.entity_id),
            position: 'right',
            distance: 5,
            fontSize: 9,
            color: tokens.inkMuted,
            fontFamily: fontSans,
            formatter: e.name,
          },
        })),
        itemStyle: { color: tokens.accent, opacity: 0.6,
                     borderColor: tokens.surface, borderWidth: 0.5 },
        labelLayout: { hideOverlap: true },
        emphasis: { label: { show: true, color: tokens.ink, fontWeight: 600 },
                    itemStyle: { opacity: 1 } },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: tokens.border, width: 1 },
          label: { show: false },
          data: [
            { xAxis: 0 },
            { yAxis: 0 },
            // The agreement diagonal: identical readings land on this line.
            [{ coord: [lo, lo], lineStyle: { type: 'dashed', color: tokens.inkMuted } },
             { coord: [hi, hi] }],
          ],
        },
      }],
    });
    const el = chartRef.current;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el);
    return () => observer.disconnect();
  }, [entities, aName, bName]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    []
  );

  return <Box ref={chartRef} sx={{ width: '100%', height }} />;
};

export default PairScatterChart;
