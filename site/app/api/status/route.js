/**
 * Is this page wired to a live ERP?
 *
 * For whoever is setting the demo up, not for the client. It answers the
 * question the page itself cannot: "I set ODOO_BASE_URL - did it actually
 * take?" Without this you are guessing from whether a trace says "sample".
 *
 * Never echoes the backend URL: the host is confirmation enough and the full
 * address stays server-side.
 */

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 6000;

export async function GET() {
  const base = process.env.ODOO_BASE_URL;
  const demoUrl = process.env.NEXT_PUBLIC_DEMO_URL || null;

  if (!base) {
    return Response.json(
      {
        connected: false,
        reason: "ODOO_BASE_URL is not set",
        traceSource: "sample",
        demoLinkShown: Boolean(demoUrl),
        hint:
          "Set ODOO_BASE_URL in Vercel > Settings > Environment Variables to the " +
          "address of a running Odoo, then redeploy. Until then the trace lookup " +
          "answers from bundled sample data.",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  }

  let host;
  try {
    host = new URL(base).host;
  } catch {
    return Response.json(
      {
        connected: false,
        reason: "ODOO_BASE_URL is not a valid URL",
        traceSource: "sample",
        hint: "It needs a scheme, e.g. https://example.app.github.dev",
      },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = Date.now();
  try {
    const res = await fetch(`${base.replace(/\/+$/, "")}/web/login`, {
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    });
    const reachable = res.status < 500;
    return Response.json(
      {
        connected: reachable,
        host,
        httpStatus: res.status,
        latencyMs: Date.now() - started,
        traceSource: reachable ? "live" : "sample",
        demoLinkShown: Boolean(demoUrl),
        hint: reachable
          ? "Trace lookups go to the live ERP."
          : "Odoo answered but with a server error. Run deploy/logs.sh on the host.",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    return Response.json(
      {
        connected: false,
        host,
        reason: err.name === "AbortError" ? "timed out" : "unreachable",
        traceSource: "sample",
        hint:
          "Common causes: the Codespace is stopped, or its port 8069 visibility " +
          "reset to private when it restarted.",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } finally {
    clearTimeout(timer);
  }
}
