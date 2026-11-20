/**
 * Inbound mail routing. Email Routing hands every message for the zone to this Worker, including
 * bounces and DMARC reports, so the decision is explicit instead of "forward everything to a human".
 */

export type InboundDecision =
  | { action: "forward"; to: string }
  | { action: "drop"; reason: string };

/** Local parts whose mail is machine-generated and should not reach the support inbox. */
const AUTOMATED = ["no-reply", "noreply", "bounce", "bounces", "mailer-daemon", "postmaster"];

export function decideInbound(recipient: string, supportInbox: string): InboundDecision {
  const address = recipient.trim().toLowerCase();
  if (!address) return { action: "drop", reason: "empty recipient" };

  const local = address.split("@")[0] ?? "";
  if (AUTOMATED.includes(local)) return { action: "drop", reason: `automated sender ${local}` };
  if (!supportInbox.trim()) return { action: "drop", reason: "no support inbox configured" };

  return { action: "forward", to: supportInbox.trim() };
}
