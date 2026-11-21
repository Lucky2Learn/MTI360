import { notFound } from "next/navigation";

// Every path of a hosted institute address other than its pages (src/proxy.ts
// rewrites them to /sites/<host>/not-found). notFound() keeps status 404 and
// renders ../not-found.tsx (Phase 02-4, ADR-0024).
export default function SitePathNotFound(): never {
  notFound();
}
