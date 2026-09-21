import { SAMPLE_LOT, SAMPLE_TRACE } from "../../../../lib/sample-trace";

/**
 * Traceability lookup for the public demo.
 *
 * With ODOO_BASE_URL set, this proxies to the live Odoo instance. Odoo's
 * `type="json"` controllers speak JSON-RPC 2.0, not plain REST, so the call
 * has to be a POST carrying an envelope and the answer is unwrapped from
 * `result` - a plain GET returns a 404 from Odoo's router.
 *
 * Proxying rather than calling Odoo from the browser keeps the backend URL out
 * of the client bundle and sidesteps CORS, which Odoo does not send by default.
 *
 * With no backend configured it answers from the bundled sample, so the page is
 * never broken in front of a client.
 */

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 8000;

function json(body, status = 200) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

async function fetchFromOdoo(base, lot) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(
      `${base.replace(/\/+$/, "")}/aifa/api/v1/traceability/${encodeURIComponent(lot)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
        signal: controller.signal,
        cache: "no-store",
      },
    );
    if (!res.ok) return { error: `backend returned ${res.status}` };

    const payload = await res.json();
    // A raised Python exception comes back as a JSON-RPC error, not an HTTP 500.
    if (payload.error) {
      return { error: payload.error?.data?.message || "backend error" };
    }
    const result = payload.result;
    if (!result || result.status !== "ok") {
      return { notFound: true };
    }
    return { traceability: result.traceability };
  } catch (err) {
    return { error: err.name === "AbortError" ? "backend timed out" : "backend unreachable" };
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(_request, { params }) {
  const { lot: raw } = await params;
  const lot = decodeURIComponent(raw || "").trim();

  if (!lot) return json({ status: "error", message: "No lot code given." }, 400);

  const base = process.env.ODOO_BASE_URL;

  if (base) {
    const out = await fetchFromOdoo(base, lot);
    if (out.traceability) {
      return json({ status: "ok", source: "live", traceability: out.traceability });
    }
    if (out.notFound) {
      return json(
        {
          status: "not_found",
          source: "live",
          message: `Lot ${lot} is not in the connected system.`,
        },
        404,
      );
    }
    // Live backend configured but unhappy: say so, and still show something.
    return json({
      status: "ok",
      source: "sample",
      degraded: out.error,
      traceability: SAMPLE_TRACE,
    });
  }

  if (lot.toUpperCase() === SAMPLE_LOT.toUpperCase()) {
    return json({ status: "ok", source: "sample", traceability: SAMPLE_TRACE });
  }

  return json(
    {
      status: "not_found",
      source: "sample",
      message:
        `This page is running without a connected ERP, so only the sample lot ` +
        `${SAMPLE_LOT} resolves.`,
    },
    404,
  );
}
