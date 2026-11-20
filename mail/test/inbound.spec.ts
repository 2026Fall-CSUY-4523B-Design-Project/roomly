import { describe, expect, it } from "vitest";

import { decideInbound } from "../src/inbound";

const SUPPORT = "support@roomly.bid";

describe("decideInbound", () => {
  it("forwards a real message to the support inbox", () => {
    expect(decideInbound("support@roomly.bid", SUPPORT)).toEqual({ action: "forward", to: SUPPORT });
    expect(decideInbound("hello@roomly.bid", SUPPORT)).toEqual({ action: "forward", to: SUPPORT });
  });

  it("forwards DMARC reports rather than dropping them", () => {
    expect(decideInbound("dmarc@roomly.bid", SUPPORT)).toEqual({ action: "forward", to: SUPPORT });
  });

  it("drops machine-generated mail so it does not bury real messages", () => {
    for (const local of ["no-reply", "noreply", "bounce", "bounces", "mailer-daemon", "postmaster"]) {
      expect(decideInbound(`${local}@roomly.bid`, SUPPORT).action).toBe("drop");
    }
  });

  it("normalises case and surrounding whitespace", () => {
    expect(decideInbound("  NO-REPLY@roomly.bid ", SUPPORT).action).toBe("drop");
    expect(decideInbound(" Support@Roomly.bid ", SUPPORT)).toEqual({ action: "forward", to: SUPPORT });
  });

  it("drops when there is nowhere to forward", () => {
    expect(decideInbound("support@roomly.bid", "").action).toBe("drop");
    expect(decideInbound("", SUPPORT).action).toBe("drop");
  });
});
