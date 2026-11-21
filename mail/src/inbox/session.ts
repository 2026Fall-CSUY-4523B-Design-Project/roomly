/**
 * The inbox login: one shared password, a signed cookie, and a failure throttle per client address.
 * No accounts: this is a support mailbox for the people who run the service.
 */

import { hmac, sameDigest } from "../sign";
import type { InboxStore } from "./store";

export const COOKIE = "inbox_session";
export const SESSION_SECONDS = 12 * 60 * 60;
export const MAX_FAILURES = 5;
export const FAILURE_WINDOW_SECONDS = 15 * 60;

/** `<expires>.<hmac>`: valid until `expires`, forged cookies fail the HMAC. */
export async function issueSession(key: string, nowSeconds: number): Promise<string> {
  const expires = nowSeconds + SESSION_SECONDS;
  return `${expires}.${await hmac(key, `inbox.${expires}`)}`;
}

export async function verifySession(key: string, cookie: string | undefined, nowSeconds: number): Promise<boolean> {
  if (!cookie) return false;
  const [expires, digest] = cookie.split(".");
  if (!expires || !digest || !/^\d{1,12}$/.test(expires)) return false;
  if (Number(expires) <= nowSeconds) return false;
  return sameDigest(await hmac(key, `inbox.${expires}`), digest);
}

export function readCookie(header: string | null, name: string): string | undefined {
  for (const part of (header ?? "").split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k === name) return rest.join("=");
  }
  return undefined;
}

/** Compare through the HMAC of each side so the check takes the same time for any input. */
export async function passwordMatches(key: string, given: string, expected: string): Promise<boolean> {
  return sameDigest(await hmac(key, `pw.${given}`), await hmac(key, `pw.${expected}`));
}

export type LoginOutcome = "ok" | "wrong" | "throttled";

export async function attemptLogin(
  store: InboxStore,
  key: string,
  expected: string,
  given: string,
  ip: string,
  nowSeconds: number,
): Promise<LoginOutcome> {
  if ((await store.recentFailures(ip, nowSeconds - FAILURE_WINDOW_SECONDS)) >= MAX_FAILURES) return "throttled";
  if (await passwordMatches(key, given, expected)) {
    await store.clearFailures(ip);
    return "ok";
  }
  await store.recordFailure(ip, nowSeconds);
  return "wrong";
}
