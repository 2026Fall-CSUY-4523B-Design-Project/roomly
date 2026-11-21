import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Env, InboundEmail, OutboundMessage } from "../src/env";
import { handleEmail, handleRequest } from "../src/index";
import { sign } from "../src/sign";

const NOW = 1_700_000_000;
const SECRET = "unit-test-secret";
const SEND_URL = "https://mail.roomly.bid/v1/send";
const TOKEN = "abc_DEF-123456789012345678";

function makeEnv(overrides: Partial<Env> = {}) {
  const sent: OutboundMessage[] = [];
  const env: Env = {
    EMAIL: {
      send: async (message) => {
        sent.push(message);
        return { messageId: "msg-1" };
      },
    },
    MAIL_SECRET: SECRET,
    APP_URL: "https://roomly.bid",
    MAIL_FROM: "Roomly <no-reply@roomly.bid>",
    SUPPORT_ADDRESS: "support@roomly.bid",
    SUPPORT_INBOX: "inbox@example.net",
    MAIL_ALLOWED_RECIPIENTS: "",
    MAIL_TRANSPORT: "email",
    ...overrides,
  };
  return { env, sent };
}

async function post(
  env: Env,
  body: string,
  options: { timestamp?: string | null; signature?: string } = {},
): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  const timestamp = options.timestamp === undefined ? String(NOW) : options.timestamp;
  if (timestamp !== null) headers["x-roomly-timestamp"] = timestamp;
  if (options.signature !== "") {
    headers["x-roomly-signature"] =
      options.signature ?? (await sign(env.MAIL_SECRET, timestamp ?? "", body));
  }
  return handleRequest(new Request(SEND_URL, { method: "POST", body, headers }), env, NOW);
}

const verifyBody = JSON.stringify({ template: "verify_email", to: "maya@example.com", data: { token: TOKEN } });

describe("handleRequest", () => {
  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports readiness without needing the mail binding", async () => {
    const { env } = makeEnv();
    const response = await handleRequest(new Request("https://mail.roomly.bid/healthz"), env, NOW);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ status: "ok", transport: "email" });
  });

  it("returns 404 for unknown routes and 405 for the wrong method", async () => {
    const { env } = makeEnv();
    expect((await handleRequest(new Request("https://mail.roomly.bid/nope"), env, NOW)).status).toBe(404);
    expect((await handleRequest(new Request(SEND_URL), env, NOW)).status).toBe(405);
  });

  it("refuses an unsigned request", async () => {
    const { env, sent } = makeEnv();
    const response = await post(env, verifyBody, { signature: "" });
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ error: { code: "missing_signature" } });
    expect(sent).toHaveLength(0);
  });

  it("refuses a replayed request after the skew window", async () => {
    const { env, sent } = makeEnv();
    const body = verifyBody;
    const response = await handleRequest(
      new Request(SEND_URL, {
        method: "POST",
        body,
        headers: {
          "x-roomly-timestamp": String(NOW),
          "x-roomly-signature": await sign(SECRET, String(NOW), body),
        },
      }),
      env,
      NOW + 3600,
    );
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ error: { code: "stale_timestamp" } });
    expect(sent).toHaveLength(0);
  });

  it("sends a verification email through the binding", async () => {
    const { env, sent } = makeEnv();
    const response = await post(env, verifyBody);
    expect(response.status).toBe(202);
    expect(await response.json()).toMatchObject({ transport: "email", template: "verify_email", id: "msg-1" });
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({ to: "maya@example.com", replyTo: "support@roomly.bid" });
    expect(sent[0]?.html).toContain(`https://roomly.bid/verify-email?token=${TOKEN}`);
  });

  it("lowercases the recipient before sending", async () => {
    const { env, sent } = makeEnv();
    const body = JSON.stringify({ template: "reset_password", to: "Maya@Example.com", data: { token: TOKEN } });
    expect((await post(env, body)).status).toBe(202);
    expect(sent[0]?.to).toBe("maya@example.com");
  });

  it("prints instead of sending when the transport is console", async () => {
    const { env, sent } = makeEnv({ MAIL_TRANSPORT: "console" });
    const response = await post(env, verifyBody);
    expect(response.status).toBe(202);
    expect(await response.json()).toMatchObject({ transport: "console" });
    expect(sent).toHaveLength(0);
  });

  it("rejects a template it does not render", async () => {
    const { env } = makeEnv();
    const body = JSON.stringify({ template: "invoice", to: "maya@example.com" });
    const response = await post(env, body);
    expect(response.status).toBe(422);
    expect(await response.json()).toMatchObject({ error: { code: "unknown_template" } });
  });

  it("rejects a bad recipient, a bad token and non-JSON bodies", async () => {
    const { env } = makeEnv();
    expect((await post(env, JSON.stringify({ template: "verify_email", to: "not-an-email" }))).status).toBe(422);
    expect(
      (await post(env, JSON.stringify({ template: "verify_email", to: "maya@example.com", data: { token: "x" } })))
        .status,
    ).toBe(422);
    expect((await post(env, "not json")).status).toBe(422);
  });

  it("honours the staging recipient allowlist", async () => {
    const { env, sent } = makeEnv({ MAIL_ALLOWED_RECIPIENTS: "steven@example.com, maya@example.com" });
    expect((await post(env, verifyBody)).status).toBe(202);
    const blocked = JSON.stringify({ template: "verify_email", to: "stranger@example.com", data: { token: TOKEN } });
    const response = await post(env, blocked);
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ error: { code: "recipient_not_allowed" } });
    expect(sent).toHaveLength(1);
  });

  it("answers 502 when Email Service rejects the message", async () => {
    const { env } = makeEnv({
      EMAIL: {
        send: async () => {
          throw Object.assign(new Error("sender not verified"), { code: "E_SENDER_NOT_VERIFIED" });
        },
      },
    });
    const response = await post(env, verifyBody);
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ error: { code: "send_failed" } });
  });
});

describe("handleEmail", () => {
  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function inbound(to: string) {
    const forwarded: string[] = [];
    const message: InboundEmail = {
      from: "person@example.com",
      to,
      rawSize: 1024,
      headers: new Headers(),
      forward: async (target) => {
        forwarded.push(target);
      },
    };
    return { message, forwarded };
  }

  it("forwards support mail to the configured inbox", async () => {
    const { env } = makeEnv();
    const { message, forwarded } = inbound("support@roomly.bid");
    await handleEmail(message, env);
    // The private inbox, not the public address: forwarding to support@roomly.bid would loop.
    expect(forwarded).toEqual(["inbox@example.net"]);
  });

  it("drops everything when no inbox is configured", async () => {
    const { env } = makeEnv({ SUPPORT_INBOX: undefined });
    const { message, forwarded } = inbound("support@roomly.bid");
    await handleEmail(message, env);
    expect(forwarded).toEqual([]);
  });

  it("drops bounces instead of forwarding them", async () => {
    const { env } = makeEnv();
    const { message, forwarded } = inbound("no-reply@roomly.bid");
    await handleEmail(message, env);
    expect(forwarded).toEqual([]);
  });
});
