/**
 * Inbound mail -> one stored row. Only plain text is kept: an HTML body is reduced to text and
 * attachments are counted but dropped, so nothing active can ever be rendered from this mailbox.
 */

import PostalMime from "postal-mime";

import type { InboundEmail } from "../env";
import type { StoredMessage } from "./store";

/** Beyond this the message is recorded without a body rather than parsed in the Worker. */
export const MAX_PARSE_BYTES = 2 * 1024 * 1024;
export const MAX_BODY_CHARS = 100_000;
const MAX_FIELD_CHARS = 500;

const ENTITIES: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " " };

export function htmlToText(html: string): string {
  return html
    .replace(/<(script|style|head)[\s\S]*?<\/\1>/gi, "")
    .replace(/<br\s*\/?>|<\/(p|div|li|tr|h[1-6])>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (entity) => ENTITIES[entity] ?? entity)
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function clip(value: string | undefined | null, max = MAX_FIELD_CHARS): string {
  // Control characters in a header have no business in a list row or a page title.
  return (value ?? "").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, " ").slice(0, max);
}

export async function toStoredMessage(
  message: InboundEmail,
  now: Date = new Date(),
  id: string = crypto.randomUUID(),
): Promise<StoredMessage> {
  const base = {
    id,
    receivedAt: now.toISOString(),
    envelopeFrom: clip(message.from),
    envelopeTo: clip(message.to).toLowerCase(),
    size: message.rawSize,
  };

  if (message.rawSize > MAX_PARSE_BYTES) {
    return {
      ...base,
      fromName: "",
      fromAddress: clip(message.from),
      subject: clip(message.headers.get("subject")),
      body: `(This message is ${message.rawSize} bytes, over the ${MAX_PARSE_BYTES} byte limit for the inbox, so its body was not stored.)`,
      attachments: 0,
      truncated: true,
      readAt: null,
    };
  }

  const email = await PostalMime.parse(message.raw);
  const text = (email.text?.trim() ? email.text : email.html ? htmlToText(email.html) : "").trimEnd();
  return {
    ...base,
    fromName: clip(email.from?.name),
    fromAddress: clip(email.from?.address || message.from),
    subject: clip(email.subject),
    body: text.slice(0, MAX_BODY_CHARS),
    attachments: email.attachments.length,
    truncated: text.length > MAX_BODY_CHARS,
    readAt: null,
  };
}
