/**
 * Transactional email copy. Text and HTML are both rendered so clients that block HTML still get
 * a working link; there are no images and no external CSS, which keeps the spam score down.
 */

export const TEMPLATE_NAMES = ["verify_email", "reset_password"] as const;
export type TemplateName = (typeof TEMPLATE_NAMES)[number];

export interface Rendered {
  subject: string;
  text: string;
  html: string;
}

/** urlsafe base64, as produced by `secrets.token_urlsafe` on the API side. */
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{16,128}$/;
const MAX_NAME_LENGTH = 60;

export type TemplateProblem = "unknown_template" | "bad_token";

export function isTemplateName(value: string): value is TemplateName {
  return (TEMPLATE_NAMES as readonly string[]).includes(value);
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function displayName(data: Record<string, unknown>): string {
  const raw = data.display_name;
  if (typeof raw !== "string") return "";
  // Control characters would land inside the subject line and the greeting.
  return raw.replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, MAX_NAME_LENGTH);
}

function layout(options: {
  heading: string;
  lead: string;
  button: string;
  link: string;
  note: string;
}): string {
  const href = escapeHtml(options.link);
  return `<!doctype html>
<html lang="en">
  <body style="margin:0;padding:24px;background:#f6f7f9;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#111827">
    <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:32px">
      <p style="margin:0 0 24px;font-size:15px;font-weight:600;letter-spacing:.02em">Roomly</p>
      <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3">${escapeHtml(options.heading)}</h1>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#374151">${escapeHtml(options.lead)}</p>
      <p style="margin:0 0 24px">
        <a href="${href}" style="display:inline-block;padding:12px 20px;background:#1f2937;color:#ffffff;border-radius:8px;text-decoration:none;font-size:15px">${escapeHtml(options.button)}</a>
      </p>
      <p style="margin:0 0 8px;font-size:13px;color:#6b7280">If the button does not work, paste this link into your browser:</p>
      <p style="margin:0 0 24px;font-size:13px;word-break:break-all"><a href="${href}" style="color:#1d4ed8">${href}</a></p>
      <p style="margin:0;font-size:13px;line-height:1.6;color:#6b7280">${escapeHtml(options.note)}</p>
    </div>
    <p style="max-width:520px;margin:16px auto 0;font-size:12px;color:#9ca3af;text-align:center">Roomly · roomly.bid</p>
  </body>
</html>`;
}

export function render(
  name: TemplateName,
  data: Record<string, unknown>,
  appUrl: string,
): Rendered {
  const token = data.token;
  if (typeof token !== "string" || !TOKEN_PATTERN.test(token)) {
    throw new TemplateProblemError("bad_token");
  }

  const base = appUrl.replace(/\/+$/, "");
  const greeting = displayName(data) ? `Hi ${displayName(data)},` : "Hello,";

  if (name === "verify_email") {
    const link = `${base}/verify-email?token=${token}`;
    const note =
      "The link works once and expires in 24 hours. If you did not create a Roomly account, you can ignore this email.";
    return {
      subject: "Confirm your Roomly email",
      text: `${greeting}\n\nConfirm this address to finish setting up your Roomly account:\n\n${link}\n\n${note}\n\nRoomly · roomly.bid\n`,
      html: layout({
        heading: "Confirm your email",
        lead: `${greeting} confirm this address to finish setting up your Roomly account.`,
        button: "Confirm email",
        link,
        note,
      }),
    };
  }

  const link = `${base}/reset-password?token=${token}`;
  const note =
    "The link works once and expires in 30 minutes. If you did not ask for a password reset, you can ignore this email: your password stays the same.";
  return {
    subject: "Reset your Roomly password",
    text: `${greeting}\n\nChoose a new password for your Roomly account:\n\n${link}\n\n${note}\n\nRoomly · roomly.bid\n`,
    html: layout({
      heading: "Reset your password",
      lead: `${greeting} use the button below to choose a new password for your Roomly account.`,
      button: "Choose a new password",
      link,
      note,
    }),
  };
}

export class TemplateProblemError extends Error {
  constructor(readonly problem: TemplateProblem) {
    super(problem);
    this.name = "TemplateProblemError";
  }
}
