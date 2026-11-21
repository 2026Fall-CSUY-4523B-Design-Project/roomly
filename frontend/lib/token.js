import { useRouter } from "next/router";
import { useEffect, useRef, useState } from "react";

// Emailed links carry a single-use token in the query string. Read it once, then take it out of the
// address bar (and so out of history and any later Referer): pages using this also send
// Referrer-Policy: no-referrer (next.config.js). `ready` is false until the router knows the query.
export function useUrlToken() {
  const router = useRouter();
  const captured = useRef(false);
  const [state, setState] = useState({ ready: false, token: "" });
  useEffect(() => {
    if (!router.isReady || captured.current) return;
    captured.current = true;
    const raw = router.query.token;
    setState({ ready: true, token: typeof raw === "string" ? raw : "" });
    if (raw !== undefined) router.replace(router.pathname, undefined, { shallow: true });
  }, [router]);
  return state;
}
