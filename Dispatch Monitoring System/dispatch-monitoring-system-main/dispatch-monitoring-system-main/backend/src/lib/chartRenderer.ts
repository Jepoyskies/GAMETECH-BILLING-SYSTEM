import { Resvg } from "@resvg/resvg-js";

interface BarSeries {
  label: string;
  values: number[];
  color: string;
}

interface PieSlice {
  label: string;
  value: number;
  color: string;
}

function escapeXml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function generateBarChartSvg(
  labels: string[],
  series: BarSeries[],
  title: string,
  width = 600,
  height = 350
): string {
  const margin = { top: 50, right: 30, bottom: 80, left: 60 };
  const chartW = width - margin.left - margin.right;
  const chartH = height - margin.top - margin.bottom;

  const allValues = series.flatMap((s) => s.values);
  const maxVal = Math.max(...allValues, 1);
  const yMax = Math.ceil(maxVal * 1.15);

  const groupWidth = chartW / labels.length;
  const barWidth = Math.max(8, (groupWidth * 0.7) / series.length);
  const gap = groupWidth * 0.15;

  let bars = "";
  let gridlines = "";

  const ySteps = 5;
  for (let i = 0; i <= ySteps; i++) {
    const yVal = Math.round((yMax / ySteps) * i);
    const yPos = margin.top + chartH - (yVal / yMax) * chartH;
    gridlines += `<line x1="${margin.left}" y1="${yPos}" x2="${width - margin.right}" y2="${yPos}" stroke="#e2e8f0" stroke-width="1"/>`;
    gridlines += `<text x="${margin.left - 8}" y="${yPos + 4}" text-anchor="end" font-size="13" fill="#64748b">${yVal}</text>`;
  }

  labels.forEach((label, i) => {
    const groupX = margin.left + i * groupWidth + gap;
    series.forEach((s, si) => {
      const barH = (s.values[i] / yMax) * chartH;
      const x = groupX + si * barWidth;
      const y = margin.top + chartH - barH;
      bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(barH, 1)}" fill="${s.color}" rx="3" ry="3"/>`;
    });

    const labelX = margin.left + i * groupWidth + groupWidth / 2;
    const maxLabelLen = 8;
    const displayLabel = label.length > maxLabelLen ? label.substring(0, maxLabelLen) + "..." : label;
    bars += `<text x="${labelX}" y="${height - margin.bottom + 20}" text-anchor="end" font-size="12" fill="#64748b" transform="rotate(-35, ${labelX}, ${height - margin.bottom + 20})">${escapeXml(displayLabel)}</text>`;
  });

  const legendY = height - 8;
  let legendHtml = "";
  series.forEach((s, i) => {
    const lx = margin.left + i * 120;
    legendHtml += `<rect x="${lx}" y="${legendY - 10}" width="12" height="12" fill="${s.color}" rx="2"/>`;
    legendHtml += `<text x="${lx + 18}" y="${legendY}" font-size="13" font-weight="bold" fill="#334155">${escapeXml(s.label)}</text>`;
  });

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" fill="#ffffff"/>
    <text x="${width / 2}" y="25" text-anchor="middle" font-size="18" font-weight="bold" fill="#1e293b">${escapeXml(title)}</text>
    ${gridlines}
    ${bars}
    ${legendHtml}
  </svg>`;
}

function generatePieChartSvg(
  slices: PieSlice[],
  title: string,
  width = 700
): string {
  const innerR = 70;
  const outerR = 110;
  const pieCenterY = 180;
  const cx = width / 2;

  const legendItemHeight = 26;
  const legendCols = slices.length > 6 ? 2 : 1;
  const legendRows = Math.ceil(slices.length / legendCols);
  const legendHeight = legendRows * legendItemHeight + 10;
  const legendGap = 30;
  const height = pieCenterY + outerR + legendGap + legendHeight + 30;

  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (total === 0) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <rect width="${width}" height="${height}" fill="#ffffff"/>
    <text x="${width / 2}" y="25" text-anchor="middle" font-size="18" font-weight="bold" fill="#1e293b">${escapeXml(title)}</text>
      <text x="${cx}" y="${pieCenterY}" text-anchor="middle" font-size="14" fill="#94a3b8">No data</text>
    </svg>`;
  }

  let cumulative = 0;
  let paths = "";

  slices.forEach((slice) => {
    if (slice.value === 0) return;
    const startAngle = (cumulative / total) * 360;
    const endAngle = ((cumulative + slice.value) / total) * 360;
    cumulative += slice.value;

    const startRad = ((startAngle - 90) * Math.PI) / 180;
    const endRad = ((endAngle - 90) * Math.PI) / 180;

    const x1 = cx + outerR * Math.cos(startRad);
    const y1 = pieCenterY + outerR * Math.sin(startRad);
    const x2 = cx + outerR * Math.cos(endRad);
    const y2 = pieCenterY + outerR * Math.sin(endRad);

    const largeArc = endAngle - startAngle > 180 ? 1 : 0;

    paths += `<path d="M ${cx + innerR * Math.cos(startRad)} ${pieCenterY + innerR * Math.sin(startRad)} L ${x1} ${y1} A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2} ${y2} L ${cx + innerR * Math.cos(endRad)} ${pieCenterY + innerR * Math.sin(endRad)} A ${innerR} ${innerR} 0 ${largeArc} 0 ${cx + innerR * Math.cos(startRad)} ${pieCenterY + innerR * Math.sin(startRad)} Z" fill="${slice.color}"/>`;
  });

  const legendTop = pieCenterY + outerR + legendGap;
  const colWidth = legendCols > 1 ? (width - 60) / legendCols : width - 60;
  let legendHtml = "";
  slices.forEach((sl, i) => {
    const col = Math.floor(i / legendRows);
    const row = i % legendRows;
    const lx = 30 + col * colWidth;
    const ly = legendTop + row * legendItemHeight;
    legendHtml += `<rect x="${lx}" y="${ly}" width="14" height="14" fill="${sl.color}" rx="3"/>`;
    legendHtml += `<text x="${lx + 22}" y="${ly + 12}" font-size="13" font-weight="bold" fill="#334155">${escapeXml(sl.label)}</text>`;
    const pct = total > 0 ? ((sl.value / total) * 100).toFixed(1) : "0";
    legendHtml += `<text x="${lx + 22}" y="${ly + 26}" font-size="12" fill="${sl.color}">${sl.value} (${pct}%)</text>`;
  });

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" fill="#ffffff"/>
    <text x="${width / 2}" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#1e293b">${escapeXml(title)}</text>
    ${paths}
    ${legendHtml}
  </svg>`;
}

export async function renderBarChartToPng(
  labels: string[],
  series: BarSeries[],
  title: string
): Promise<Uint8Array> {
  const svg = generateBarChartSvg(labels, series, title);
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: 800 * 2 },
    logLevel: "off",
  });
  const rendered = resvg.render();
  return rendered.asPng();
}

interface PieChartResult {
  png: Uint8Array;
  width: number;
  height: number;
}

export async function renderPieChartToPng(
  slices: PieSlice[],
  title: string
): Promise<PieChartResult> {
  const svgWidth = 700;
  const svg = generatePieChartSvg(slices, title, svgWidth);
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: svgWidth * 2 },
    logLevel: "off",
  });
  const rendered = resvg.render();
  const img = rendered.asPng();
  const logicalWidth = svgWidth;
  const logicalHeight = Math.ceil(rendered.height / 2);
  return { png: img, width: logicalWidth, height: logicalHeight };
}

export type { BarSeries, PieSlice, PieChartResult };
