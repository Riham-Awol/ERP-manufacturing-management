import YieldChart from "../components/YieldChart";
import TraceDemo from "../components/TraceDemo";

const REPO = "https://github.com/Riham-Awol/ERP-manufacturing-management";
const DEMO_URL = process.env.NEXT_PUBLIC_DEMO_URL || "";

const MODULES = [
  {
    tag: "FRS-M1",
    name: "Outgrower sourcing",
    body: "Farmer and plot registry with GPS, a dated farm-gate price matrix, and field purchases captured offline at the depot and replayed idempotently when there is signal. The agent never types a price.",
  },
  {
    tag: "FRS-M2 · M3",
    name: "Dehydration processing",
    body: "Three-stage BOMs, prep logs with scrap broken down by cause, and dehydration runs carrying profile, moisture, water activity and kWh. A prep log that does not balance cannot be confirmed.",
  },
  {
    tag: "FRS-M4",
    name: "Quality & food safety",
    body: "HACCP control points with critical limits. A failure on a blocking point quarantines the lot automatically and opens a non-conformance report that will not close without a root cause.",
  },
  {
    tag: "FRS-4.5",
    name: "Farm-to-shelf traceability",
    body: "Lot genealogy resolved back through all three manufacturing stages to the farm gate, recall simulation that also reaches consigned stock on retail shelves, and the public QR page.",
  },
  {
    tag: "FRS-M6",
    name: "Consignment & route sales",
    body: "Shelf stock stays on Aifa's balance sheet until a count proves it sold, then bills exactly that. Van routes settle at end of day so nothing quietly becomes shrinkage.",
  },
  {
    tag: "FRS-M8",
    name: "KPIs & ESG impact",
    body: "Nightly plant snapshots with the yield gap valued in birr, and a P4G/CARE impact statement built from dated, cited, per-crop assumptions rather than a hard-coded loss rate.",
  },
];

const STAGES = [
  ["00", "Farm gate", "Weigh, grade, price, pay"],
  ["01", "Reception", "Gate QA, lot assigned"],
  ["02", "Preparation", "Wash CCP-1, peel, slice"],
  ["03", "Dehydration", "Chamber run, profile, kWh"],
  ["04", "Conditioning", "Moisture & aw gate"],
  ["05", "Packing", "Metal detect, check-weigh"],
  ["06", "Distribution", "Consignment, route sales"],
];

export default function Page() {
  return (
    <>
      {/* ---------------- hero ---------------- */}
      <section className="hero">
        <div className="wrap">
          <div className="eyebrow">Yarashoo Agro Industry PLC · Aifa Foods</div>
          <h1>An ERP that knows what happens to the fruit.</h1>
          <p className="lede">
            Seven custom Odoo Community modules for farm-gate sourcing, dehydration yield
            control, HACCP gates and farm-to-shelf traceability. Built, installed on a clean
            database, and driven through a complete production cycle.
          </p>

          <div className="badges">
            <span className="badge">Odoo 17 Community · LGPLv3</span>
            <span className="badge">Zero licence fees</span>
            <span className="badge">Proposal v3.0</span>
          </div>

          <div className="btn-row">
            {DEMO_URL ? (
              <a className="btn btn-primary" href={DEMO_URL} target="_blank" rel="noreferrer">
                Open the live system
              </a>
            ) : (
              <a className="btn btn-primary" href="#trace">
                Trace a pack
              </a>
            )}
            <a className="btn btn-ghost" href={REPO} target="_blank" rel="noreferrer">
              Source &amp; documentation
            </a>
          </div>

          <div className="stats" style={{ marginTop: 34 }}>
            <div className="stat">
              <div className="value">7</div>
              <div className="label">modules built and verified</div>
            </div>
            <div className="stat">
              <div className="value">26</div>
              <div className="label">FRS requirements implemented</div>
            </div>
            <div className="stat">
              <div className="value">&lt; 1s</div>
              <div className="label">pouch traced back to the farm</div>
            </div>
            <div className="stat">
              <div className="value">0 ETB</div>
              <div className="label">software licence cost, ever</div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- finding ---------------- */}
      <section id="finding">
        <div className="wrap">
          <div className="eyebrow">What the build changed</div>
          <h2>One ratio does not fit three crops</h2>
          <p>
            The v2.4 proposal applied a single 8:1&ndash;10:1 fresh-to-dry ratio across the
            range. That holds for pineapple and is generous for mango. It is substantially
            wrong for tomato, which is roughly 94% water.
          </p>
          <p>
            Budgeting a tomato line on the pineapple factor understates the raw fruit
            requirement for that line by about half &mdash; in sourcing volume, in working
            capital and in factory loading.
          </p>

          <YieldChart />

          <div className="note">
            <p>
              These are calibrated baselines, not measurements of your plant. They live in
              the crop master record, per crop and per cultivar, and Phase 1 replaces them
              with three trial batches each. Changing them is master data, not code.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- workflow ---------------- */}
      <section id="workflow">
        <div className="wrap">
          <div className="eyebrow">The process</div>
          <h2>Seven stages, each one a record rather than a memory</h2>
          <p>
            Every arrow below is a point where mass changes hands or changes state. The
            system&rsquo;s job is to make each one auditable.
          </p>
          <div className="flow" style={{ marginTop: 22 }}>
            {STAGES.map(([n, name, detail]) => (
              <div className="flow-step" key={n}>
                <div className="n">{n}</div>
                <strong>{name}</strong>
                <span>{detail}</span>
              </div>
            ))}
          </div>
          <div className="note">
            <p>
              The workflow is written down in full, with every assumption tagged by source
              and twelve open questions for discovery. We are not pretending to know your
              line better than you do.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- built ---------------- */}
      <section id="built">
        <div className="wrap">
          <div className="eyebrow">What exists today</div>
          <h2>Not slideware</h2>
          <p>
            All seven modules install together on a clean Odoo 17 Community database and
            were driven end to end by a scripted run: field purchase &rarr; gate QA &rarr;
            prep &rarr; dehydration &rarr; release testing &rarr; packing &rarr;
            check-weighing &rarr; consignment &rarr; invoice &rarr; recall drill.
          </p>
          <div className="grid grid-3" style={{ marginTop: 22 }}>
            {MODULES.map((m) => (
              <div className="card" key={m.name}>
                <span className="tag">{m.tag}</span>
                <h3>{m.name}</h3>
                <p>{m.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- trace ---------------- */}
      <section id="trace">
        <div className="wrap">
          <div className="eyebrow">Live</div>
          <h2>Trace a pack back to the farm</h2>
          <p>
            This is what the QR code on a retail pouch resolves to. Today, tracing a
            finished pack back to a farmer takes over 48 hours of paper. Here it is one
            lookup.
          </p>
          <div style={{ marginTop: 20 }}>
            <TraceDemo />
          </div>
        </div>
      </section>

      {/* ---------------- honest ---------------- */}
      <section id="scope">
        <div className="wrap">
          <div className="eyebrow">Scope, stated plainly</div>
          <h2>What is not built, and why</h2>
          <div className="grid grid-2" style={{ marginTop: 18 }}>
            <div className="card">
              <h3>MoR fiscal device integration</h3>
              <p>
                We can calculate VAT, withholding and turnover tax and produce an
                export-ready invoice payload. We cannot certify an integration with a
                device whose current specification we have not been given. Go-live should
                not depend on it; run the dual-track approach and scope the digital sync
                as a follow-on.
              </p>
            </div>
            <div className="card">
              <h3>Amharic across the whole interface</h3>
              <p>
                Every string in our modules is translatable and will be translated. Core
                Odoo&rsquo;s own Amharic coverage is partial, so some standard screens stay
                in English. Budget a translation review rather than assuming completeness.
              </p>
            </div>
            <div className="card">
              <h3>The offline mobile client</h3>
              <p>
                The server side is built and tested, including idempotent replay of a
                buying session captured with no signal. The phone application itself is a
                separate build, inside the existing commercial line item.
              </p>
            </div>
            <div className="card">
              <h3>Harvest volume forecasting</h3>
              <p>
                Deferred. It needs a full season of plot-level actuals, and a forecast
                built on data that does not exist yet is a number nobody should trust. The
                plot register captures the inputs from day one.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- next ---------------- */}
      <section id="next">
        <div className="wrap">
          <div className="eyebrow">Next step</div>
          <h2>One week, and we need your line</h2>
          <p>
            Phase 1 is a walk of the plant and three trial batches per crop, so the yield
            standards become yours rather than ours. Everything downstream &mdash; costing,
            capacity, every variance alert &mdash; depends on those numbers being real.
          </p>
          <div className="btn-row" style={{ marginTop: 18 }}>
            <a className="btn btn-primary" href={`${REPO}/blob/claude/focused-davinci-b8f4ki/docs/02-PROPOSAL.md`} target="_blank" rel="noreferrer">
              Read the proposal
            </a>
            <a className="btn btn-ghost" href={`${REPO}/blob/claude/focused-davinci-b8f4ki/docs/01-WORKFLOW-BLUEPRINT.md`} target="_blank" rel="noreferrer">
              The workflow blueprint
            </a>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap">
          Prepared for Yarashoo Agro Industry PLC / Aifa Foods. Figures on this page come
          from a verified build, not from projections. Source and full documentation:{" "}
          <a href={REPO} target="_blank" rel="noreferrer">
            github.com/Riham-Awol/ERP-manufacturing-management
          </a>
        </div>
      </footer>
    </>
  );
}
