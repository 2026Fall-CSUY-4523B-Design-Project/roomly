import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

import Field from "@/components/Field";
import { api } from "@/lib/api";
import { safeNext, saveSession } from "@/lib/auth";

import styles from "@/styles/auth.module.css";

// Account creation (§8.1.2.1, R-1.1). The backend validates; these limits only guide typing.
export default function SignUpPage() {
  const router = useRouter();
  const next = safeNext(router.query.next, "/groups");
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = { ...form, display_name: form.display_name.trim() || null };
      saveSession(await api.signUp(body));
      router.replace(next);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <div className={styles.wrap}>
      <Head>
        <title>Create account · Roomly</title>
      </Head>
      <div className={`card ${styles.panel}`}>
        <p className="eyebrow">Start your search</p>
        <h1>Create your account</h1>
        <p className="muted">Save searches, form a group of up to six, and decide on a place together.</p>
        <form className={styles.form} onSubmit={submit} noValidate>
          {error && !Object.keys(error.fields).length ? (
            <div className="alert alert-error" role="alert">
              {error.message}
            </div>
          ) : null}
          <Field
            id="display_name"
            label="Name (optional)"
            autoComplete="nickname"
            maxLength={60}
            value={form.display_name}
            onChange={set("display_name")}
            error={error?.fields.display_name}
            hint="What your group sees. Leave it blank to appear as &ldquo;Member&rdquo;."
          />
          <Field
            id="email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={set("email")}
            error={error?.fields.email}
          />
          <Field
            id="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={form.password}
            onChange={set("password")}
            error={error?.fields.password}
            hint="At least 8 characters."
          />
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className={styles.switch}>
          Already have an account?{" "}
          <Link href={`/sign-in?next=${encodeURIComponent(next)}`}>
            <a>Sign in</a>
          </Link>
        </p>
      </div>
    </div>
  );
}
