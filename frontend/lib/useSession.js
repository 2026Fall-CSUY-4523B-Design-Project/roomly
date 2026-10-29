import { useEffect, useState } from "react";

import { loadSession, onSessionChange } from "./auth.js";

// { session, ready }. The server render knows no session, so `ready` stays false until the
// browser has read storage; pages wait for it instead of flashing "signed out".
export function useSession() {
  const [state, setState] = useState({ session: null, ready: false });
  useEffect(() => {
    setState({ session: loadSession(), ready: true });
    return onSessionChange((session) => setState({ session, ready: true }));
  }, []);
  return state;
}
