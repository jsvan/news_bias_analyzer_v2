import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Card, CardHeader, CardContent, Box, Typography } from '@mui/material';
import { tokens, fontSans } from '../theme';

// The lossless view: every pairwise correlation drawn as itself, no 2-D
// projection (the MDS map's stress is exactly what this panel doesn't have).
// Rows/columns follow the server's seriation (optimal dendrogram-leaf order
// on the same weighted-average-linkage geometry the clusters are cut from),
// so constellations appear as warm blocks on the diagonal and a source that
// straddles two groups shows as a band crossing into the neighboring block.
// Cell opacity is the significance weight - thin overlaps look faint, not
// confident - and unknown pairs render gray: "not enough shared coverage to
// say", never "dissimilar". Click any cell for the pair's entity scatter.

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent,
              CanvasRenderer]);

interface MatrixSource {
  source_id: number;
  name: string;
  country: string | null;
  cluster: string | null;
}

interface MatrixPair {
  source_id_1: number;
  source_id_2: number;
  score: number;
  common_entities: number;
}

interface Matrix {
  sources: MatrixSource[];
  pairs: MatrixPair[];
  order?: number[] | null;
}

const SIGNIFICANCE_FULL = 50; // mirrors the backend's significance_weight

const SimilarityMatrixPanel: React.FC<{
  matrix: Matrix | null;
  onPairClick: (a: MatrixSource, b: MatrixSource, r: number, common: number) => void;
}> = ({ matrix, onPairClick }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onPairClick);
  clickRef.current = onPairClick;

  const model = useMemo(() => {
    if (!matrix?.order || matrix.order.length < 3) return null;
    const byId = new Map(matrix.sources.map((s) => [s.source_id, s]));
    const ordered = matrix.order
      .map((id) => byId.get(id))
      .filter((s): s is MatrixSource => !!s);
    const index = new Map(ordered.map((s, i) => [s.source_id, i]));
    const known: any[] = [];
    const seen = new Set<string>();
    for (const p of matrix.pairs) {
      const i = index.get(p.source_id_1);
      const j = index.get(p.source_id_2);
      if (i === undefined || j === undefined) continue;
      const opacity = 0.25 + 0.75 * Math.min(p.common_entities / SIGNIFICANCE_FULL, 1);
      // Both triangles: the square matrix reads better than a triangle.
      known.push({ value: [i, j, p.score], common: p.common_entities,
                   itemStyle: { opacity } });
      known.push({ value: [j, i, p.score], common: p.common_entities,
                   itemStyle: { opacity } });
      seen.add(`${i}_${j}`);
      seen.add(`${j}_${i}`);
    }
    const unknown: number[][] = [];
    for (let i = 0; i < ordered.length; i++) {
      known.push({ value: [i, i, 1], common: null, itemStyle: { opacity: 0.9 } });
      for (let j = 0; j < ordered.length; j++) {
        if (i !== j && !seen.has(`${i}_${j}`)) unknown.push([i, j]);
      }
    }
    return { ordered, known, unknown };
  }, [matrix]);

  useEffect(() => {
    if (!model || !chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
      chartInstance.current.on('click', (params: any) => {
        if (params.seriesIndex !== 0) return;
        const [i, j] = params.value;
        if (i === j) return;
        const cur = (chartInstance.current as any).__model;
        if (!cur) return;
        clickRef.current(cur.ordered[i], cur.ordered[j],
                         params.value[2], params.data.common ?? 0);
      });
    }
    const chart = chartInstance.current;
    (chart as any).__model = model;
    const names = model.ordered.map((s) => s.name);

    const axisCommon = {
      type: 'category' as const,
      data: names,
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { show: false },
    };

    chart.setOption({
      animation: false,
      grid: { top: 8, right: 90, bottom: 110, left: 130 },
      xAxis: {
        ...axisCommon,
        position: 'bottom',
        axisLabel: { fontSize: 8, rotate: 90, interval: 0,
                     color: tokens.inkMuted, fontFamily: fontSans },
      },
      yAxis: {
        ...axisCommon,
        inverse: true, // same order top->bottom as left->right
        axisLabel: { fontSize: 8, interval: 0,
                     color: tokens.inkMuted, fontFamily: fontSans },
      },
      visualMap: {
        type: 'continuous',
        min: -1,
        max: 1,
        calculable: false,
        seriesIndex: [0],
        orient: 'vertical',
        right: 8,
        top: 'middle',
        itemHeight: 120,
        itemWidth: 12,
        text: ['r = +1', 'r = −1'],
        textStyle: { fontSize: 10, color: tokens.inkMuted, fontFamily: fontSans },
        inRange: { color: [tokens.villain, '#EEF0F3', tokens.accent] },
      },
      tooltip: {
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (p: any) => {
          const [i, j] = p.value;
          if (p.seriesIndex === 1) {
            return `${names[i]} × ${names[j]}<br/>` +
              `<span style="color:${tokens.inkMuted};font-size:11px">` +
              `not enough shared coverage to compare</span>`;
          }
          if (i === j) return names[i];
          return `${names[i]} × ${names[j]}<br/>` +
            `<span style="color:${tokens.inkMuted};font-size:11px">` +
            `r = ${p.value[2] >= 0 ? '+' : ''}${p.value[2].toFixed(2)} · ` +
            `${p.data.common} shared entities · click for detail</span>`;
        },
      },
      series: [
        {
          type: 'heatmap',
          data: model.known,
          itemStyle: { borderColor: tokens.surface, borderWidth: 0.5 },
          emphasis: { itemStyle: { borderColor: tokens.ink, borderWidth: 1 } },
          progressive: 0,
        },
        {
          type: 'heatmap',
          data: model.unknown,
          itemStyle: { color: tokens.surfaceSunken, opacity: 0.5,
                       borderColor: tokens.surface, borderWidth: 0.5 },
          silent: false,
          progressive: 0,
        },
      ],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [model]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    []
  );

  if (!model) return null;
  const side = Math.max(480, model.ordered.length * 11 + 240);

  return (
    <Card>
      <CardHeader
        title="The full matrix"
        subheader="Every pairwise correlation, drawn losslessly — rows ordered so groups form blocks on the diagonal"
      />
      <CardContent sx={{ pt: 0 }}>
        <Box ref={chartRef} sx={{ width: '100%', height: side }} />
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
          Teal cells agree, red cells systematically invert each other, and faint cells rest
          on thin overlap (opacity is confidence). Gray means the two sources didn't share
          enough coverage to compare — visibly unknown rather than silently zero. The row
          order is the dendrogram's optimal leaf order, so the diagonal runs along the
          smoothest similarity gradient; a warm band leaking out of a block is a source that
          straddles two groups. Click any cell to see exactly which entities the pair reads
          differently.
        </Typography>
      </CardContent>
    </Card>
  );
};

export default SimilarityMatrixPanel;
