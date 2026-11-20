import { describe, expect, it } from "vitest";

import { render, TemplateProblemError } from "../src/templates";

const TOKEN = "abc_DEF-123456789012345678";

describe("render", () => {
  it("links a verification to /verify-email on the configured site", () => {
    const mail = render("verify_email", { token: TOKEN }, "https://roomly.bid/");
    expect(mail.subject).toBe("Confirm your Roomly email");
    expect(mail.text).toContain(`https://roomly.bid/verify-email?token=${TOKEN}`);
    expect(mail.html).toContain(`href="https://roomly.bid/verify-email?token=${TOKEN}"`);
    expect(mail.text).toContain("24 hours");
  });

  it("links a reset to /reset-password and says the password is unchanged if ignored", () => {
    const mail = render("reset_password", { token: TOKEN }, "https://roomly.bid");
    expect(mail.subject).toBe("Reset your Roomly password");
    expect(mail.text).toContain(`https://roomly.bid/reset-password?token=${TOKEN}`);
    expect(mail.text).toContain("30 minutes");
    expect(mail.text).toContain("your password stays the same");
  });

  it("greets by display name in the body, never in the subject", () => {
    const mail = render("verify_email", { token: TOKEN, display_name: "Maya" }, "https://roomly.bid");
    expect(mail.text.startsWith("Hi Maya,")).toBe(true);
    expect(mail.subject).not.toContain("Maya");
  });

  it("escapes a display name that looks like markup", () => {
    const mail = render(
      "verify_email",
      { token: TOKEN, display_name: '<script>alert("x")</script>' },
      "https://roomly.bid",
    );
    expect(mail.html).not.toContain("<script>");
    expect(mail.html).toContain("&lt;script&gt;");
  });

  it("falls back to a plain greeting when no name is given", () => {
    const mail = render("verify_email", { token: TOKEN }, "https://roomly.bid");
    expect(mail.text.startsWith("Hello,")).toBe(true);
  });

  it("rejects a token that could break out of the link or the markup", () => {
    for (const token of ["short", `${TOKEN}"onmouseover="x`, `${TOKEN}?next=https://evil.test`, "a".repeat(129)]) {
      expect(() => render("verify_email", { token }, "https://roomly.bid")).toThrowError(TemplateProblemError);
    }
  });

  it("rejects a missing token", () => {
    expect(() => render("reset_password", {}, "https://roomly.bid")).toThrowError(TemplateProblemError);
  });

  it("always ships both a text and an html part", () => {
    for (const name of ["verify_email", "reset_password"] as const) {
      const mail = render(name, { token: TOKEN }, "https://roomly.bid");
      expect(mail.text.length).toBeGreaterThan(0);
      expect(mail.html.startsWith("<!doctype html>")).toBe(true);
      expect(mail.html).not.toContain("<img");
    }
  });
});
