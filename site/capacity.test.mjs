import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { analyze, parseCsv } from "./capacity.js";

const csv = readFileSync(new URL("./sample_analytics.csv", import.meta.url), "utf8");
const golden = JSON.parse(readFileSync(new URL("../tests/fixtures/capacity_golden.json", import.meta.url), "utf8"));

test("the site copy of the sample data is the same file as data/", () => {
  assert.equal(csv, readFileSync(new URL("../data/sample_analytics.csv", import.meta.url), "utf8"));
});

test("JavaScript result equals the Python golden result", () => {
  const { series, ...result } = analyze(parseCsv(csv), 100);
  assert.deepEqual(result, golden);
});

test("flat traffic has no estimate", () => {
  const rows = [1, 2, 3].map((d) => ({ ts: `2026-11-0${d}T10:00:00+00:00`, proxy: "a", tps: 10, p99: 100 }));
  assert.equal(analyze(rows, 100).days_to_threshold, null);
});

test("past the threshold reports zero", () => {
  const rows = [90, 91].map((t, i) => ({ ts: `2026-11-0${i + 1}T10:00:00+00:00`, proxy: "a", tps: t, p99: 100 }));
  assert.equal(analyze(rows, 100).days_to_threshold, 0);
});
