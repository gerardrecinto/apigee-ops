// JavaScript port of src/apigee_ops/capacity.py. capacity.test.mjs checks it against the Python golden result.
// Timestamps are ISO 8601 in UTC (the sample data is), so the day is the first 10 characters.

export function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const head = lines.shift().split(",");
  return lines.map((line) => {
    const c = line.split(",");
    const r = Object.fromEntries(head.map((h, i) => [h, c[i]]));
    return { ts: r.timestamp, proxy: r.proxy, tps: +r.tps, p99: +r.p99_ms };
  });
}

function fit(points) {
  const n = points.length;
  if (n < 2) return [n ? points[0][1] : 0, 0];
  let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (const [x, y] of points) { sx += x; sy += y; sxx += x * x; sxy += x * y; }
  const den = n * sxx - sx * sx;
  if (den === 0) return [sy / n, 0];
  const b = (n * sxy - sx * sy) / den;
  return [(sy - b * sx) / n, b];
}

const round = (x, d) => Number(x.toFixed(d));
const dayNumber = (day) => Date.UTC(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10)) / 86400000;

export function analyze(rows, capacity, threshold = 0.8) {
  if (!rows.length) throw new Error("no rows to analyze");
  const peak = {}, worstP99 = {}, totalAt = {};
  for (const r of rows) {
    peak[r.proxy] = Math.max(peak[r.proxy] ?? 0, r.tps);
    worstP99[r.proxy] = Math.max(worstP99[r.proxy] ?? 0, r.p99);
    totalAt[r.ts] = (totalAt[r.ts] ?? 0) + r.tps;
  }
  const daily = {};
  for (const [ts, tps] of Object.entries(totalAt)) {
    const day = ts.slice(0, 10);
    daily[day] = Math.max(daily[day] ?? 0, tps);
  }
  const days = Object.keys(daily).sort();
  const first = dayNumber(days[0]);
  const points = days.map((d) => [dayNumber(d) - first, daily[d]]);
  const [a, slope] = fit(points);
  const current = a + slope * points[points.length - 1][0];
  const limit = capacity * threshold;
  let daysToThreshold = null;
  if (current >= limit) daysToThreshold = 0;
  else if (slope > 0) daysToThreshold = round((limit - current) / slope, 1);
  const peakTotal = Math.max(...Object.values(daily));
  return {
    capacity_tps: capacity,
    threshold,
    peak_total_tps: round(peakTotal, 2),
    headroom_pct: round((1 - peakTotal / capacity) * 100, 1),
    growth_tps_per_day: round(slope, 3),
    days_to_threshold: daysToThreshold,
    proxies: Object.fromEntries(Object.keys(peak).sort().map((p) => [p, { peak_tps: round(peak[p], 2), worst_p99_ms: round(worstP99[p], 1) }])),
    series: { days, daily: days.map((d) => daily[d]), a, slope },
  };
}
