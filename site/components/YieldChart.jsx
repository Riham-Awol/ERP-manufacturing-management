"use client";

import { useId, useState } from "react";

/**
 * Fresh-to-dried ratio by crop, against the single 8:1-10:1 band the v2.4
 * proposal applied to all three.
 *
 * One measure across three entities, so it is a single series: every bar takes
 * the same validated blue rather than a colour per crop. Tomato's outlier
 * status is carried by bar length and a direct label, not by hue.
 */

const DATA = [
  { crop: "Mango", ratio: 7.7, prep: 65, dry: 20, note: "peel and stone ≈ 35% of prep loss" },
  { crop: "Pineapple", ratio: 10.7, prep: 55, dry: 17, note: "crown, shell and core ≈ 45%" },
  { crop: "Tomato", ratio: 14.6, prep: 95, dry: 7.2, note: "≈ 94% water; only the calyx is trimmed" },
];

const ASSUMED = [8, 10];
const MAX = 16;

const W = 720;
const ROW_H = 54;
const BAR_H = 26;
const PAD_L = 104;
const PAD_R = 58;
const PAD_T = 34;
const PAD_B = 34;
const H = PAD_T + DATA.length * ROW_H + PAD_B;
const PLOT_W = W - PAD_L - PAD_R;

const x = (v) => PAD_L + (v / MAX) * PLOT_W;

/** Bar with a 4px rounded data-end, square against the baseline. */
function barPath(x0, x1, y, h, r = 4) {
  const len = x1 - x0;
  if (len <= r) return `M${x0},${y} H${x1} V${y + h} H${x0} Z`;
  return [
    `M${x0},${y}`,
    `H${x1 - r}`,
    `A${r},${r} 0 0 1 ${x1},${y + r}`,
    `V${y + h - r}`,
    `A${r},${r} 0 0 1 ${x1 - r},${y + h}`,
    `H${x0}`,
    "Z",
  ].join(" ");
}

export default function YieldChart() {
  const titleId = useId();
  const [hover, setHover] = useState(null);
  const [showTable, setShowTable] = useState(false);

  const ticks = [0, 4, 8, 12, 16];

  return (
    <figure style={{ margin: "22px 0 0" }}>
      <figcaption style={{ marginBottom: 10 }}>
        <strong style={{ fontSize: "1rem" }}>
          Kilograms of fresh fruit needed for 1 kg of dried product
        </strong>
        <div style={{ fontSize: ".88rem", color: "var(--text-muted)", marginTop: 2 }}>
          Shaded band is the single 8:1–10:1 ratio the v2.4 proposal applied to every crop.
        </div>
      </figcaption>

      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "8px 4px 4px",
          position: "relative",
        }}
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-labelledby={titleId}
          style={{ display: "block", overflow: "visible" }}
          onMouseLeave={() => setHover(null)}
        >
          <title id={titleId}>
            Fresh-to-dried ratio: mango 7.7 to 1, pineapple 10.7 to 1, tomato 14.6 to 1.
            The v2.4 proposal assumed 8 to 1 through 10 to 1 for all three.
          </title>

          {/* assumed band - recessive, behind the data */}
          <rect
            x={x(ASSUMED[0])}
            y={PAD_T - 12}
            width={x(ASSUMED[1]) - x(ASSUMED[0])}
            height={DATA.length * ROW_H + 14}
            fill="var(--text-primary)"
            opacity="0.06"
          />
          <text
            x={(x(ASSUMED[0]) + x(ASSUMED[1])) / 2}
            y={PAD_T - 18}
            textAnchor="middle"
            fontSize="11"
            fill="var(--text-muted)"
          >
            v2.4 assumption
          </text>

          {/* grid */}
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={PAD_T - 4}
                y2={PAD_T + DATA.length * ROW_H}
                stroke="var(--border)"
                strokeWidth="1"
              />
              <text
                x={x(t)}
                y={PAD_T + DATA.length * ROW_H + 18}
                textAnchor="middle"
                fontSize="11"
                fill="var(--text-muted)"
              >
                {t}
              </text>
            </g>
          ))}

          {DATA.map((d, i) => {
            const y = PAD_T + i * ROW_H + (ROW_H - BAR_H) / 2;
            const isHot = hover === i;
            return (
              <g
                key={d.crop}
                onMouseEnter={() => setHover(i)}
                style={{ cursor: "default" }}
              >
                {/* generous hit target */}
                <rect
                  x={0}
                  y={PAD_T + i * ROW_H}
                  width={W}
                  height={ROW_H}
                  fill="transparent"
                />
                <text
                  x={PAD_L - 12}
                  y={y + BAR_H / 2 + 4}
                  textAnchor="end"
                  fontSize="13"
                  fill="var(--text-primary)"
                  fontWeight={isHot ? 650 : 500}
                >
                  {d.crop}
                </text>
                <path
                  d={barPath(x(0), x(d.ratio), y, BAR_H)}
                  fill="var(--series-1)"
                  opacity={hover === null || isHot ? 1 : 0.55}
                />
                <text
                  x={x(d.ratio) + 8}
                  y={y + BAR_H / 2 + 4}
                  fontSize="13"
                  fontWeight="650"
                  fill="var(--text-primary)"
                >
                  {d.ratio.toFixed(1)}:1
                </text>
              </g>
            );
          })}
        </svg>

        {hover !== null && (
          <div
            role="status"
            style={{
              position: "absolute",
              left: 12,
              bottom: 8,
              background: "var(--surface-0)",
              border: "1px solid var(--border-strong)",
              borderRadius: 8,
              padding: "8px 11px",
              fontSize: ".84rem",
              maxWidth: "min(460px, 92%)",
              boxShadow: "0 6px 20px rgba(0,0,0,.10)",
            }}
          >
            <strong>{DATA[hover].crop}</strong> — prep yield {DATA[hover].prep}%, drying
            yield {DATA[hover].dry}% → <strong>{DATA[hover].ratio.toFixed(1)}:1</strong>
            <div style={{ color: "var(--text-muted)", marginTop: 2 }}>
              {DATA[hover].note}
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowTable((v) => !v)}
        style={{
          marginTop: 10,
          background: "none",
          border: 0,
          padding: 0,
          color: "var(--text-secondary)",
          fontSize: ".85rem",
          textDecoration: "underline",
          cursor: "pointer",
        }}
      >
        {showTable ? "Hide the numbers" : "Show the numbers"}
      </button>

      {showTable && (
        <div className="tbl-wrap" style={{ marginTop: 10 }}>
          <table className="tbl">
            <caption>
              Calibrated baselines carried in the crop master record. Phase 1 replaces
              them with Aifa&rsquo;s own trial batches.
            </caption>
            <thead>
              <tr>
                <th>Crop</th>
                <th className="num">Prep yield</th>
                <th className="num">Drying yield</th>
                <th className="num">Fresh : dried</th>
                <th className="num">v2.4 assumed</th>
              </tr>
            </thead>
            <tbody>
              {DATA.map((d) => (
                <tr key={d.crop}>
                  <td>{d.crop}</td>
                  <td className="num">{d.prep}%</td>
                  <td className="num">{d.dry}%</td>
                  <td className="num">
                    <strong>{d.ratio.toFixed(1)}:1</strong>
                  </td>
                  <td className="num">8–10:1</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
