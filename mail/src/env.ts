/**
 * Bindings and variables the Worker needs. Declared here rather than generated so the project
 * builds the same way in CI, where no wrangler type output exists.
 */

/** Structured message accepted by the `send_email` binding (Email Service, Workers API). */
export interface OutboundMessage {
  to: string;
  from: string;
  subject: string;
  html: string;
  text: string;
  replyTo?: string;
}

export interface EmailSender {
  send(message: OutboundMessage): Promise<{ messageId: string }>;
}

/** The part of `ForwardableEmailMessage` this Worker uses for inbound mail. */
export interface InboundEmail {
  readonly from: string;
  readonly to: string;
  readonly rawSize: number;
  readonly headers: Headers;
  readonly raw: ReadableStream<Uint8Array>;
  forward(to: string): Promise<void>;
  setReject(reason: string): void;
}

/** The slice of the D1 API the inbox uses. */
export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  run(): Promise<{ meta: { changes: number } }>;
  all<T = Record<string, unknown>>(): Promise<{ results: T[] }>;
  first<T = Record<string, unknown>>(): Promise<T | null>;
}

export interface D1Database {
  prepare(sql: string): D1PreparedStatement;
}

export interface Env {
  EMAIL: EmailSender;
  /** Shared with the API: signs every POST /v1/send. Set with `wrangler secret put`. */
  MAIL_SECRET: string;
  /** Public site URL used in links; the API decides it per environment. */
  APP_URL: string;
  /** Envelope sender, e.g. `Roomly <no-reply@roomly.bid>`. Must be on the onboarded domain. */
  MAIL_FROM: string;
  /** The public address people write to, e.g. `support@roomly.bid`. Used as Reply-To on outbound mail. */
  SUPPORT_ADDRESS: string;
  /**
   * Where inbound mail (support, replies, DMARC reports) is forwarded: a real mailbox outside the
   * domain that is a verified destination in Email Routing. Private, so it is a Worker secret
   * (`wrangler secret put SUPPORT_INBOX`) and never in this public repository. Unset = inbound mail
   * is logged and dropped.
   */
  SUPPORT_INBOX?: string;
  /** The inbox database (D1). Without it the web inbox is off and inbound mail is only forwarded. */
  DB?: D1Database;
  /** Password for the web inbox. A Worker secret; unset keeps the inbox login closed. */
  INBOX_PASSWORD?: string;
  /** Signs the inbox session cookie. A Worker secret, any long random string. */
  INBOX_SESSION_KEY?: string;
  /** Comma-separated allowlist; when set, sends to anything else are rejected. Staging only. */
  MAIL_ALLOWED_RECIPIENTS?: string;
  /** `email` (default) sends through the binding; `console` prints for local runs. */
  MAIL_TRANSPORT?: "email" | "console";
}
