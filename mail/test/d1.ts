/** A D1-shaped adapter over node:sqlite, so the inbox's real SQL runs in tests without Cloudflare. */

import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

import type { D1Database, D1PreparedStatement } from "../src/env";

export function memoryD1(): D1Database & { sql: DatabaseSync } {
  const sql = new DatabaseSync(":memory:");
  sql.exec(readFileSync(new URL("../migrations/0001_inbox.sql", import.meta.url), "utf8"));
  return {
    sql,
    prepare(query: string): D1PreparedStatement {
      const statement = sql.prepare(query);
      let values: never[] = [];
      const api: D1PreparedStatement = {
        bind(...v: unknown[]) {
          values = v as never[];
          return api;
        },
        async run() {
          return { meta: { changes: Number(statement.run(...values).changes) } };
        },
        async all<T>() {
          return { results: statement.all(...values) as T[] };
        },
        async first<T>() {
          return (statement.get(...values) as T | undefined) ?? null;
        },
      };
      return api;
    },
  };
}
