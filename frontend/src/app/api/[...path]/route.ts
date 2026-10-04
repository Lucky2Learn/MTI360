import { proxyToApi } from "@/lib/api/proxy";
import { getServerEnv } from "@/lib/env";

// Same-origin API proxy route (T01-09A, D17): /api/v1/* → API_BASE_URL.
// Behaviour, header allow-lists and logging rules: lib/api/proxy.ts.

export const dynamic = "force-dynamic";

function forward(request: Request): Promise<Response> {
  const { apiBaseUrl, trustedProxyHops } = getServerEnv();
  return proxyToApi(request, { apiBaseUrl, trustedProxyHops });
}

export {
  forward as DELETE,
  forward as GET,
  forward as PATCH,
  forward as POST,
  forward as PUT,
};
