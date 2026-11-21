/**
 * The inbox's storage, behind one interface so the handlers never see SQL and the tests can run the
 * real statements against SQLite.
 */

import type { D1Database } from "../env";

export interface StoredMessage {
  id: string;
  receivedAt: string;
  envelopeFrom: string;
  envelopeTo: string;
  fromName: string;
  fromAddress: string;
  subject: string;
  body: string;
  size: number;
  attachments: number;
  truncated: boolean;
  readAt: string | null;
}

export type MessageSummary = Omit<StoredMessage, "body">;

export interface ListQuery {
  to?: string;
  q?: string;
  limit: number;
  offset: number;
}

export interface Page {
  messages: MessageSummary[];
  total: number;
  unread: number;
}

export interface InboxStore {
  insert(message: StoredMessage): Promise<void>;
  list(query: ListQuery): Promise<Page>;
  get(id: string): Promise<StoredMessage | null>;
  markRead(id: string, at: string): Promise<void>;
  remove(id: string): Promise<boolean>;
  recipients(): Promise<{ address: string; count: number }[]>;
  purgeOlderThan(isoCutoff: string, unixCutoff: number): Promise<number>;
  recentFailures(ip: string, sinceUnix: number): Promise<number>;
  recordFailure(ip: string, atUnix: number): Promise<void>;
  clearFailures(ip: string): Promise<void>;
}

interface Row {
  id: string;
  received_at: string;
  envelope_from: string;
  envelope_to: string;
  from_name: string;
  from_address: string;
  subject: string;
  body?: string;
  size: number;
  attachments: number;
  truncated: number;
  read_at: string | null;
}

const SUMMARY_COLUMNS =
  "id, received_at, envelope_from, envelope_to, from_name, from_address, subject, size, attachments, truncated, read_at";

function summary(row: Row): MessageSummary {
  return {
    id: row.id,
    receivedAt: row.received_at,
    envelopeFrom: row.envelope_from,
    envelopeTo: row.envelope_to,
    fromName: row.from_name,
    fromAddress: row.from_address,
    subject: row.subject,
    size: row.size,
    attachments: row.attachments,
    truncated: row.truncated === 1,
    readAt: row.read_at,
  };
}

/** Escape LIKE wildcards so a search for `50%` means 50%, with `\` as the escape character. */
function likePattern(value: string): string {
  return `%${value.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
}

export class D1Store implements InboxStore {
  constructor(private readonly db: D1Database) {}

  async insert(m: StoredMessage): Promise<void> {
    await this.db
      .prepare(
        `INSERT INTO message (id, received_at, envelope_from, envelope_to, from_name, from_address,
                              subject, body, size, attachments, truncated, read_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)`,
      )
      .bind(m.id, m.receivedAt, m.envelopeFrom, m.envelopeTo, m.fromName, m.fromAddress, m.subject, m.body,
        m.size, m.attachments, m.truncated ? 1 : 0)
      .run();
  }

  async list(query: ListQuery): Promise<Page> {
    const where: string[] = [];
    const params: unknown[] = [];
    if (query.to) {
      where.push("envelope_to = ?");
      params.push(query.to.toLowerCase());
    }
    if (query.q) {
      where.push("(subject LIKE ? ESCAPE '\\' OR from_address LIKE ? ESCAPE '\\' OR from_name LIKE ? ESCAPE '\\' OR envelope_to LIKE ? ESCAPE '\\')");
      const like = likePattern(query.q);
      params.push(like, like, like, like);
    }
    const clause = where.length > 0 ? `WHERE ${where.join(" AND ")}` : "";
    const rows = await this.db
      .prepare(`SELECT ${SUMMARY_COLUMNS} FROM message ${clause} ORDER BY received_at DESC, id LIMIT ? OFFSET ?`)
      .bind(...params, query.limit, query.offset)
      .all<Row>();
    const counts = await this.db
      .prepare(`SELECT COUNT(*) AS total, COALESCE(SUM(read_at IS NULL), 0) AS unread FROM message ${clause}`)
      .bind(...params)
      .first<{ total: number; unread: number }>();
    return {
      messages: rows.results.map(summary),
      total: counts?.total ?? 0,
      unread: counts?.unread ?? 0,
    };
  }

  async get(id: string): Promise<StoredMessage | null> {
    const row = await this.db.prepare("SELECT * FROM message WHERE id = ?").bind(id).first<Row>();
    return row ? { ...summary(row), body: row.body ?? "" } : null;
  }

  async markRead(id: string, at: string): Promise<void> {
    await this.db.prepare("UPDATE message SET read_at = ? WHERE id = ? AND read_at IS NULL").bind(at, id).run();
  }

  async remove(id: string): Promise<boolean> {
    const result = await this.db.prepare("DELETE FROM message WHERE id = ?").bind(id).run();
    return result.meta.changes > 0;
  }

  async recipients(): Promise<{ address: string; count: number }[]> {
    const rows = await this.db
      .prepare("SELECT envelope_to AS address, COUNT(*) AS count FROM message GROUP BY envelope_to ORDER BY MAX(received_at) DESC LIMIT 20")
      .all<{ address: string; count: number }>();
    return rows.results;
  }

  async purgeOlderThan(isoCutoff: string, unixCutoff: number): Promise<number> {
    const removed = await this.db.prepare("DELETE FROM message WHERE received_at < ?").bind(isoCutoff).run();
    await this.db.prepare("DELETE FROM login_failure WHERE at < ?").bind(unixCutoff).run();
    return removed.meta.changes;
  }

  async recentFailures(ip: string, sinceUnix: number): Promise<number> {
    const row = await this.db
      .prepare("SELECT COUNT(*) AS n FROM login_failure WHERE ip = ? AND at >= ?")
      .bind(ip, sinceUnix)
      .first<{ n: number }>();
    return row?.n ?? 0;
  }

  async recordFailure(ip: string, atUnix: number): Promise<void> {
    await this.db.prepare("INSERT INTO login_failure (ip, at) VALUES (?, ?)").bind(ip, atUnix).run();
  }

  async clearFailures(ip: string): Promise<void> {
    await this.db.prepare("DELETE FROM login_failure WHERE ip = ?").bind(ip).run();
  }
}
