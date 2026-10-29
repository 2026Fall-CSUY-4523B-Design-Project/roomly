import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

import Field from "@/components/Field";
import { api } from "@/lib/api";
import { safeNext, saveSession } from "@/lib/auth";

import styles from "@/styles/auth.module.css";

export default function SignInPage() {
  const router = useRouter();
  const next = safeNext(router.query.next, "/groups");
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      saveSession(await api.signIn(form));
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
        <title>Sign in · Roomly</title>
      </Head>
      <div className={`card ${styles.panel}`}>
        <p className="eyebrow">Welcome back</p>
        <h1>Sign in</h1>
        <form className={styles.form} onSubmit={submit} noValidate>
          {error && !Object.keys(error.fields).length ? (
            <div className="alert alert-error" role="alert">
              {error.message}
            </div>
          ) : null}
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
            autoComplete="current-password"
            required
            value={form.password}
            onChange={set("password")}
            error={error?.fields.password}
          />
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className={styles.switch}>
          New to Roomly?{" "}
          <Link href={`/sign-up?next=${encodeURIComponent(next)}`}>
            <a>Create an account</a>
          </Link>
        </p>
      </div>
    </div>
  );
}
