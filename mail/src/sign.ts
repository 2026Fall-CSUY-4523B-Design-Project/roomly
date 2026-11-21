/**
 * Request signing for POST /v1/send.
 *
 * The API and this Worker share one secret. A request carries the unix timestamp it was made at
 * and `v1=<hex>` over `<timestamp>.<raw body>`, so a captured request stops working after the
 * skew window and replaying it later cannot slip through.
 */

const encoder = new TextEncoder();

export const SIGNATURE_PREFIX = "v1=";
export const MAX_CLOCK_SKEW_SECONDS = 300;

export type SignatureProblem = "missing_signature" | "stale_timestamp" | "bad_signature";

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function hmac(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toHex(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
}

/** Whether two hex strings are equal without an early exit on the first differing byte. */
export function sameDigest(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function sign(
  secret: string,
  timestamp: string,
  body: string,
): Promise<string> {
  return `${SIGNATURE_PREFIX}${await hmac(secret, `${timestamp}.${body}`)}`;
}

/** `null` when the request is authentic, otherwise why it is not. */
export async function verifySignature(
  secret: string,
  timestamp: string | null,
  signature: string | null,
  body: string,
  nowSeconds: number = Math.floor(Date.now() / 1000),
): Promise<SignatureProblem | null> {
  if (!timestamp || !signature) return "missing_signature";
  if (!/^\d{1,12}$/.test(timestamp)) return "stale_timestamp";
  if (Math.abs(nowSeconds - Number(timestamp)) > MAX_CLOCK_SKEW_SECONDS) return "stale_timestamp";
  if (!signature.startsWith(SIGNATURE_PREFIX)) return "missing_signature";
  const expected = await sign(secret, timestamp, body);
  return sameDigest(expected.slice(SIGNATURE_PREFIX.length), signature.slice(SIGNATURE_PREFIX.length))
    ? null
    : "bad_signature";
}
