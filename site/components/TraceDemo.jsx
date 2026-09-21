"use client";

import { useState } from "react";
import { SAMPLE_LOT } from "../lib/sample-trace";

export default function TraceDemo() {
  const [lot, setLot] = useState(SAMPLE_LOT);
  const [state, setState] = useState({ status: "idle" });

  async function lookup(e) {
    e?.preventDefault();
    const code = lot.trim();
    if (!code) return;
    setState({ status: "loading" });
    try {
      const res = await fetch(`/api/trace/${encodeURIComponent(code)}`);
      const body = await res.json();
      setState(
        body.status === "ok"
          ? { status: "ok", ...body }
          : { status: "not_found", message: body.message },
      );
    } catch {
      setState({ status: "error", message: "Could not reach the lookup service." });
    }
  }

  const t = state.status === "ok" ? state.traceability : null;

  return (
    <div>
      <form onSubmit={lookup} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <label htmlFor="lot" className="sr-only">
          Lot code from the pack
        </label>
        <input
          id="lot"
          value={lot}
          onChange={(e) => setLot(e.target.value)}
          placeholder="Lot code from the pack"
          style={{
            flex: "1 1 280px",
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid var(--border-strong)",
            background: "var(--surface-0)",
            color: "var(--text-primary)",
            fontSize: ".95rem",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          }}
        />
        <button className="btn btn-primary" type="submit">
          {state.status === "loading" ? "Tracing…" : "Trace"}
        </button>
      </form>

      <div style={{ fontSize: ".84rem", color: "var(--text-muted)", marginTop: 8 }}>
        Try <code>{SAMPLE_LOT}</code> — a real finished-goods lot from a seeded run.
      </div>

      {state.status === "not_found" && (
        <div className="note" style={{ borderLeftColor: "var(--status-warning)" }}>
          <p>{state.message}</p>
        </div>
      )}

      {state.status === "error" && (
        <div className="note" style={{ borderLeftColor: "var(--status-critical)" }}>
          <p>{state.message}</p>
        </div>
      )}

      {t && (
        <div style={{ marginTop: 18 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
              marginBottom: 14,
            }}
          >
            <span className={`pill ${t.released ? "pill-good" : "pill-warning"}`}>
              {t.released ? "✓ Quality released" : `⚠ ${t.quality_state}`}
            </span>
            <span style={{ fontSize: ".82rem", color: "var(--text-muted)" }}>
              {state.source === "live"
                ? "Live from the connected ERP"
                : "Bundled sample — no ERP connected"}
            </span>
            {state.degraded && (
              <span style={{ fontSize: ".82rem", color: "var(--status-critical)" }}>
                ({state.degraded})
              </span>
            )}
          </div>

          <h3 style={{ marginBottom: 2 }}>{t.product}</h3>
          <p style={{ fontSize: ".88rem", marginBottom: 18 }}>
            Lot <code>{t.lot}</code>
            {t.expiry ? ` · best before ${t.expiry}` : ""}
          </p>

          <div className="grid grid-2">
            <div className="card">
              <span className="tag">Where it grew</span>
              <table className="tbl">
                <tbody>
                  <tr>
                    <th>Region</th>
                    <td>{t.regions?.join(", ") || "—"}</td>
                  </tr>
                  <tr>
                    <th>Cooperative</th>
                    <td>{t.cooperatives?.join(", ") || "—"}</td>
                  </tr>
                  <tr>
                    <th>Outgrowers</th>
                    <td>
                      {t.outgrower_count}
                      {t.women_outgrower_pct
                        ? ` (${Math.round(t.women_outgrower_pct)}% women)`
                        : ""}
                    </td>
                  </tr>
                  <tr>
                    <th>Harvested</th>
                    <td>{t.harvest_dates?.join(", ") || "—"}</td>
                  </tr>
                  <tr>
                    <th>Fresh fruit</th>
                    <td>{t.fresh_fruit_kg?.toLocaleString()} kg</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="card">
              <span className="tag">How it was dried</span>
              {t.drying_runs?.length ? (
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Chamber</th>
                        <th className="num">Temp</th>
                        <th className="num">Hours</th>
                        <th className="num">Moisture</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.drying_runs.map((r, i) => (
                        <tr key={i}>
                          <td>{r.chamber}</td>
                          <td className="num">{r.avg_temp_c} °C</td>
                          <td className="num">{r.hours}</td>
                          <td className="num">{r.moisture_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>No drying record linked.</p>
              )}
              {t.checks?.length ? (
                <ul style={{ margin: "12px 0 0", paddingLeft: 18, fontSize: ".88rem" }}>
                  {t.checks.map((c, i) => (
                    <li key={i} style={{ color: "var(--text-secondary)" }}>
                      <span
                        style={{
                          color:
                            c.result === "pass"
                              ? "var(--status-good)"
                              : "var(--status-critical)",
                        }}
                      >
                        {c.result === "pass" ? "✓" : "✕"}
                      </span>{" "}
                      {c.point} — {c.value} {c.unit}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>

          <div className="note" style={{ marginTop: 16 }}>
            <p>
              No farmer name, phone number or price appears here, by design. A consumer
              scanning the pack sees provenance; personal and commercial data stay
              inside the ERP.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
