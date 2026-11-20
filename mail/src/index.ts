/**
 * Roomly mail Worker.
 *
 *   POST /v1/send   signed transactional mail from the API (verification, password reset)
 *   GET  /healthz   readiness, without touching the mail binding
 *   email()         inbound mail for roomly.bid, forwarded to the support inbox
 *
 * The Worker never renders user input into headers, only into the body, and every request must be
 * signed by the API so the endpoint cannot be used as an open relay.
 */

import type { Env, InboundEmail } from "./env";
import { decideInbound } from "./inbound";
import { verifySignature } from "./sign";
import { isTemplateName, render, TemplateProblemError } from "./templates";

const MAX_BODY_BYTES = 32 * 1024;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function json(status: number, body: unknown): Response {
  return new Response(`${JSON.stringify(body)}\n`, {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function fail(status: number, code: string, message: string): Response {
  return json(status, { error: { code, message } });
}

function allowedRecipients(env: Env): string[] {
  return (env.MAIL_ALLOWED_RECIPIENTS ?? "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
}

export async function handleRequest(
  request: Request,
  env: Env,
  nowSeconds: number = Math.floor(Date.now() / 1000),
): Promise<Response> {
  const { pathname } = new URL(request.url);

  if (pathname === "/healthz") {
    if (request.method !== "GET") return fail(405, "method_not_allowed", "Use GET.");
    return json(200, {
      status: "ok",
      transport: env.MAIL_TRANSPORT === "console" ? "console" : "email",
      templates: ["verify_email", "reset_password"],
    });
  }

  if (pathname !== "/v1/send") return fail(404, "not_found", "Unknown route.");
  if (request.method !== "POST") return fail(405, "method_not_allowed", "Use POST.");
  if (!env.MAIL_SECRET) return fail(500, "not_configured", "MAIL_SECRET is not set.");

  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) return fail(413, "body_too_large", "Request body is too large.");

  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) {
    return fail(413, "body_too_large", "Request body is too large.");
  }

  const problem = await verifySignature(
    env.MAIL_SECRET,
    request.headers.get("x-roomly-timestamp"),
    request.headers.get("x-roomly-signature"),
    body,
    nowSeconds,
  );
  if (problem === "stale_timestamp") {
    return fail(401, problem, "Timestamp is outside the accepted window.");
  }
  if (problem) return fail(401, problem, "Signature is missing or does not match.");

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return fail(422, "invalid_body", "Body must be JSON.");
  }
  if (typeof payload !== "object" || payload === null) {
    return fail(422, "invalid_body", "Body must be a JSON object.");
  }

  const { template, to, data } = payload as Record<string, unknown>;
  if (typeof template !== "string" || !isTemplateName(template)) {
    return fail(422, "unknown_template", "Template is not one the Worker renders.");
  }
  if (typeof to !== "string" || !EMAIL_PATTERN.test(to.trim().toLowerCase())) {
    return fail(422, "bad_recipient", "`to` must be an email address.");
  }
  if (data !== undefined && (typeof data !== "object" || data === null || Array.isArray(data))) {
    return fail(422, "invalid_body", "`data` must be an object.");
  }

  const recipient = to.trim().toLowerCase();
  const allowlist = allowedRecipients(env);
  if (allowlist.length > 0 && !allowlist.includes(recipient)) {
    return fail(403, "recipient_not_allowed", "Recipient is outside MAIL_ALLOWED_RECIPIENTS.");
  }

  let rendered;
  try {
    rendered = render(template, (data ?? {}) as Record<string, unknown>, env.APP_URL);
  } catch (error) {
    if (error instanceof TemplateProblemError) return fail(422, error.problem, "Template data is invalid.");
    throw error;
  }

  if (env.MAIL_TRANSPORT === "console") {
    console.log(JSON.stringify({ transport: "console", template, to: recipient, subject: rendered.subject }));
    return json(202, { transport: "console", template, to: recipient });
  }

  try {
    const result = await env.EMAIL.send({
      to: recipient,
      from: env.MAIL_FROM,
      subject: rendered.subject,
      html: rendered.html,
      text: rendered.text,
      replyTo: env.SUPPORT_INBOX,
    });
    return json(202, { transport: "email", template, to: recipient, id: result.messageId });
  } catch (error) {
    const code = (error as { code?: string }).code ?? "unknown";
    const message = error instanceof Error ? error.message : String(error);
    console.error(JSON.stringify({ event: "send_failed", template, to: recipient, code, message }));
    return fail(502, "send_failed", "Email Service rejected the message.");
  }
}

export async function handleEmail(message: InboundEmail, env: Env): Promise<void> {
  const decision = decideInbound(message.to, env.SUPPORT_INBOX);
  if (decision.action === "drop") {
    console.log(JSON.stringify({ event: "inbound_dropped", to: message.to, from: message.from, reason: decision.reason }));
    return;
  }
  try {
    await message.forward(decision.to);
    console.log(JSON.stringify({ event: "inbound_forwarded", to: message.to, from: message.from, target: decision.to }));
  } catch (error) {
    // Accepting and logging beats rejecting: a bounce only tells the sender we are broken.
    console.error(JSON.stringify({ event: "inbound_forward_failed", to: message.to, message: String(error) }));
  }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handleRequest(request, env);
  },
  email(message: InboundEmail, env: Env): Promise<void> {
    return handleEmail(message, env);
  },
};
