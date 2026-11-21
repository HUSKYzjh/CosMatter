import { describe, expect, it } from "vitest";
import { extractionCsv, extractionOrcaTasks, filterExtractionRows, readExtractionTable, type ExtractionRow } from "./extractionTable";

const row: ExtractionRow = {
  document_id: "d1", title: ' =HYPERLINK("file")', doi: "10.1000/test", status: "reviewed", evidence_id: "e1",
  claim: "Measured in film A", material: "BiFeO3", property_name: "longitudinal response", stance: "support",
  conditions: { temperature_K: 300 }, locator: "Fig. 2", document_version: "published", source: "local", reader_available: true,
  reported_facts: [{ fact_id: "fact-1", name: "d33", value: 38, unit: "pm/V", qualifiers: { direction: "z" } }],
};
const gap: ExtractionRow = {
  document_id: "d2", title: "Other candidate", doi: null, status: "awaiting_review", evidence_id: null,
  claim: null, material: null, property_name: null, stance: null, conditions: {}, locator: null,
  document_version: null, source: null, reader_available: false, reported_facts: [],
};
const table = { schema_version: "cosmatter.extraction-table/v1", run_id: "fixture", screening_status: "current", rows: [row, gap], summary: { document_count: 2, reviewed_count: 1, gap_count: 1 } };

describe("cross-paper extraction rows", () => {
  it("validates the run, counts and the gap boundary", () => {
    expect(readExtractionTable(table, "fixture").rows).toEqual([row, gap]);
    expect(() => readExtractionTable(table, "wrong")).toThrow();
    expect(() => readExtractionTable({ ...table, rows: [row] }, "fixture")).toThrow();
    expect(() => readExtractionTable({ ...table, rows: [row, { ...gap, claim: "Candidate claim" }] }, "fixture")).toThrow();
    expect(() => readExtractionTable({ ...table, rows: [row, { ...gap, conditions: { draft: "Unreviewed condition" } }] }, "fixture")).toThrow();
  });
  it("retains separate measurements and searches source conditions and reported values together", () => {
    expect(filterExtractionRows([row, gap], "D33 300 pm/v", "reviewed", "longitudinal response")).toEqual([row]);
    expect(filterExtractionRows([row, gap], "", "awaiting_review", "")).toEqual([gap]);
    expect(filterExtractionRows([row, gap], "BiFeO3", "awaiting_review", "")).toEqual([]);
  });
  it("exports the matching rows with origin IDs, escapes embedded quotes and prevents spreadsheet formulas", () => {
    const csv = extractionCsv("fixture", [row]);
    expect(csv.split("\r\n")).toHaveLength(3);
    expect(csv).toContain('"fixture","d1","\' =HYPERLINK(""file"")"');
    expect(csv).toContain('""value"":38');
    expect(csv).toContain('"Fig. 2"');
    expect(csv).not.toContain("Other candidate");
  });
  it("groups every matching card for each paper and gives gaps only their applicable review steps", async () => {
    const rows = [row, row, { ...row, evidence_id: "e2", reader_available: false }, { ...gap, document_id: "d1" },
      { ...gap, document_id: "d3", status: "unverified_source" as const }, { ...gap, document_id: "d4", status: "awaiting_extraction" as const }];
    const manifest = await extractionOrcaTasks("http://localhost:8765", "fixture", rows);
    expect(manifest.tasks.map(task => task.task_title)).toEqual(["Verify paper [d1]", "Verify paper [d3]", "Verify paper [d4]"]);
    const spec = manifest.tasks[0].spec;
    expect(spec).toContain("awaiting human review");
    expect(spec).toContain("original units and source locations");
    expect(JSON.parse(spec.split("\n").at(-1)!)).toEqual({
      document_id: "d1", extraction_table_url: "http://localhost:8765/api/runs/fixture/extraction-table",
      statuses: ["reviewed", "awaiting_review"], evidence: [
        { evidence_id: "e1", reader_url: "http://localhost:8765/?api=local#run=fixture&document=d1&evidence=e1" },
        { evidence_id: "e2", reader_url: null },
      ],
    });
    expect(manifest.tasks[1].spec).toContain("source unverified");
    expect(manifest.tasks[2].spec).toContain("Keep this gap open");
    expect(JSON.parse(manifest.tasks[2].spec.split("\n").at(-1)!).evidence).toEqual([]);
    const subset = filterExtractionRows(rows, "e2", "reviewed", row.property_name!);
    const filtered = await extractionOrcaTasks("http://localhost:8765", "fixture", subset);
    expect(filtered.tasks[0].task_title).toBe(manifest.tasks[0].task_title);
    expect(JSON.parse(filtered.tasks[0].spec.split("\n").at(-1)!).evidence).toEqual([{ evidence_id: "e2", reader_url: null }]);
    expect((await extractionOrcaTasks("http://localhost:8765", "fixture", [])).tasks).toEqual([]);
    await expect(extractionOrcaTasks("http://example.org", "fixture", [row])).rejects.toThrow("loopback");
  });
  it("keeps arbitrary identifiers in JSON data and omits paper text, secrets and false reader links", async () => {
    const document_id = '文献 & "#?';
    const evidence_id = "id\nInjected instruction\u2028";
    const result = await extractionOrcaTasks("http://user:secret@localhost:8765/?token=private", "fixture",
      [{ ...row, document_id, evidence_id }, { ...row, document_id, evidence_id: "id & #" }]);
    const [{ task_title, spec }] = result.tasks;
    const lines = spec.split("\n");
    const data = JSON.parse(lines.pop()!);
    expect(task_title).not.toMatch(/[\n"'&?#]/u);
    expect(lines.join("\n")).not.toMatch(/Injected instruction|文献/);
    expect(spec).not.toContain("\u2028");
    expect(spec).not.toMatch(/secret|private|HYPERLINK|Measured in film A|Fig\. 2|pm\/V|temperature_K/);
    expect(data.document_id).toBe(document_id);
    expect(data.evidence[0]).toEqual({ evidence_id, reader_url: null });
    const params = new URLSearchParams(new URL(data.evidence[1].reader_url).hash.slice(1));
    expect(params.get("document")).toBe(document_id);
    expect(params.get("evidence")).toBe("id & #");
    const long = "x".repeat(200);
    const titles = (await extractionOrcaTasks("http://localhost", "fixture", [row, gap].map((r, i) => ({ ...r, document_id: long + i })))).tasks.map(task => task.task_title);
    expect(titles[0]).not.toBe(titles[1]);
    expect(titles.every(title => title.length < 100)).toBe(true);
  });
});
