export function resolveCorsOrigins(): boolean | string[] {
  const raw = process.env.CORS_ORIGINS;
  if (!raw || !raw.trim()) return true;
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
