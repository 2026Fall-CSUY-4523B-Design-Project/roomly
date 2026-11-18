import { createContext, useContext, useEffect, useState } from "react";

import { accountRequest } from "@/lib/api";

const AuthContext = createContext(null);
const STORAGE_KEY = "roomly.session";

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function clearSession() {
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }

  useEffect(() => {
    let active = true;
    async function restore() {
      try {
        const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
        if (!saved) return;
        if (!saved.token || Date.parse(saved.expires_at) <= Date.now()) {
          sessionStorage.removeItem(STORAGE_KEY);
          return;
        }
        const user = await accountRequest("/me", { token: saved.token });
        if (active) setSession({ ...saved, user });
      } catch (err) {
        if (err.status === 401 || err instanceof SyntaxError) sessionStorage.removeItem(STORAGE_KEY);
        else if (active) setError("Could not restore your session. Please reload to try again.");
      } finally {
        if (active) setLoading(false);
      }
    }
    restore();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => {
      clearSession();
      setError("Your session has expired. Please sign in again.");
    }, Math.max(0, Date.parse(session.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [session]);

  async function signIn(path, body) {
    const result = await accountRequest(path, { method: "POST", body });
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token: result.token, expires_at: result.expires_at }));
    } catch {
      await accountRequest("/auth/sign-out", { method: "POST", token: result.token });
      throw new Error("Allow browser session storage to sign in.");
    }
    setError("");
    setSession(result);
  }

  async function signOut() {
    setError("");
    try {
      await accountRequest("/auth/sign-out", { method: "POST", token: session.token });
      clearSession();
    } catch (err) {
      if (err.status === 401) clearSession();
      else setError("Could not sign out. Please try again.");
    }
  }

  return <AuthContext.Provider value={{ user: session?.user, loading, error, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
