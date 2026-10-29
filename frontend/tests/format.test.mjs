import assert from "node:assert/strict";
import { test } from "node:test";

import { UNKNOWN, bedrooms, borough, date, dollarsToCents, money, plural } from "../lib/format.js";

test("money formats integer cents and labels null as Unknown", () => {
  assert.equal(money(300_000), "$3,000");
  assert.equal(money(250_050), "$2,500.50");
  assert.equal(money(0), "$0");
  assert.equal(money(null), UNKNOWN);
  assert.equal(money(undefined), UNKNOWN);
});

test("dollarsToCents parses what people type, rejects nonsense", () => {
  assert.equal(dollarsToCents("2,400"), 240_000);
  assert.equal(dollarsToCents(" $3200.5 "), 320_050);
  assert.equal(dollarsToCents(""), null);
  assert.ok(Number.isNaN(dollarsToCents("abc")));
  assert.ok(Number.isNaN(dollarsToCents("1.234")));
  assert.ok(Number.isNaN(dollarsToCents("-5")));
});

test("bedrooms, boroughs and plurals read naturally", () => {
  assert.equal(bedrooms(0), "Studio");
  assert.equal(bedrooms(1), "1 bed");
  assert.equal(bedrooms(3), "3 beds");
  assert.equal(bedrooms(null), "Unknown beds");
  assert.equal(borough("staten_island"), "Staten Island");
  assert.equal(borough(null), UNKNOWN);
  assert.equal(plural(1, "listing"), "1 listing");
  assert.equal(plural(1200, "listing"), "1,200 listings");
});

test("a calendar date never shifts a day west of UTC", () => {
  const tz = process.env.TZ;
  process.env.TZ = "America/Los_Angeles";
  try {
    assert.equal(date("2026-11-03"), "Nov 3, 2026");
    assert.equal(date("2026-11-03T12:00:00.000000+00:00"), "Nov 3, 2026");
  } finally {
    process.env.TZ = tz;
  }
  assert.equal(date(null), UNKNOWN);
  assert.equal(date("not a date"), UNKNOWN);
});
