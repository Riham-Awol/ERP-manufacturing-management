/**
 * Offline fallback for the traceability demo.
 *
 * This is not invented data: it is the verbatim payload returned by
 * POST /aifa/api/v1/traceability/<lot> on a seeded Odoo instance after
 * tools/seed_demo.py ran a complete farm-to-shelf cycle. It is used when no
 * ODOO_BASE_URL is configured, or when the live backend cannot be reached, so
 * the demo still works on a plane.
 */

export const SAMPLE_LOT = "LOT-FG-PINE100-20260920";

export const SAMPLE_TRACE = {
  lot: SAMPLE_LOT,
  product: "[AIFA-PINE-100] Aifa Dried Pineapple Slices 100g",
  released: true,
  quality_state: "released",
  expiry: "20 September 2027",
  regions: ["Gamo / Arba Minch"],
  cooperatives: ["Gamo Women Fruit Growers Union"],
  outgrower_count: 2,
  women_outgrower_pct: 100.0,
  harvest_dates: ["2026-09-14"],
  fresh_fruit_kg: 878.4,
  drying_runs: [
    {
      chamber: "Tunnel Dehydrator 1",
      date: "2026-09-20",
      avg_temp_c: 64.0,
      hours: 16.0,
      moisture_pct: 13.2,
      water_activity: 0.56,
    },
  ],
  checks: [
    { point: "Water Activity after Conditioning", result: "pass", value: 0.56, unit: "aw" },
    { point: "Residual Moisture after Drying", result: "pass", value: 13.2, unit: "% moisture" },
  ],
};
