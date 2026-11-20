import { describe, expect, it } from "vitest";

import { sign, verifySignature } from "../src/sign";

const SECRET = "unit-test-secret";
const NOW = 1_700_000_000;
const TIMESTAMP = String(NOW);
const BODY = '{"template":"verify_email","to":"maya@example.com"}';

describe("verifySignature", () => {
  it("accepts a body signed at the same instant", async () => {
    expect(await verifySignature(SECRET, TIMESTAMP, await sign(SECRET, TIMESTAMP, BODY), BODY, NOW)).toBeNull();
  });

  it("rejects a body that changed after signing", async () => {
    const signature = await sign(SECRET, TIMESTAMP, BODY);
    const tampered = BODY.replace("maya@example.com", "someone@example.com");
    expect(await verifySignature(SECRET, TIMESTAMP, signature, tampered, NOW)).toBe("bad_signature");
  });

  it("rejects a signature from another secret", async () => {
    const signature = await sign("other-secret", TIMESTAMP, BODY);
    expect(await verifySignature(SECRET, TIMESTAMP, signature, BODY, NOW)).toBe("bad_signature");
  });

  it("rejects a timestamp outside the five minute window", async () => {
    const signature = await sign(SECRET, TIMESTAMP, BODY);
    expect(await verifySignature(SECRET, TIMESTAMP, signature, BODY, NOW + 301)).toBe("stale_timestamp");
    expect(await verifySignature(SECRET, TIMESTAMP, signature, BODY, NOW - 301)).toBe("stale_timestamp");
  });

  it("still accepts a slightly late request, so clock drift does not break deploys", async () => {
    const signature = await sign(SECRET, TIMESTAMP, BODY);
    expect(await verifySignature(SECRET, TIMESTAMP, signature, BODY, NOW + 240)).toBeNull();
  });

  it("rejects requests without a signature or timestamp", async () => {
    expect(await verifySignature(SECRET, null, null, BODY, NOW)).toBe("missing_signature");
    expect(await verifySignature(SECRET, TIMESTAMP, null, BODY, NOW)).toBe("missing_signature");
    expect(await verifySignature(SECRET, null, await sign(SECRET, TIMESTAMP, BODY), BODY, NOW)).toBe(
      "missing_signature",
    );
  });

  it("rejects a signature without the version prefix", async () => {
    const signature = (await sign(SECRET, TIMESTAMP, BODY)).slice("v1=".length);
    expect(await verifySignature(SECRET, TIMESTAMP, signature, BODY, NOW)).toBe("missing_signature");
  });
});
