import styles from "./SprintNotice.module.css";

// The honest placeholder for a screen that is not built yet: which sprint delivers it, what it
// will do, and which API endpoints already serve it. Dates follow the SSDS v2.0 sprint plan.
export const SPRINTS = {
  3: { name: "Sprint 3", window: "Oct 21 – Nov 3" },
  4: { name: "Sprint 4", window: "Nov 4 – 17" },
  5: { name: "Sprint 5", window: "Nov 18 – 30" },
  6: { name: "Sprint 6", window: "Dec 1 – 15" },
};

export default function SprintNotice({ sprint, title, children, items = [], endpoints = [], compact = false }) {
  const s = SPRINTS[sprint];
  return (
    <section className={`${styles.notice} ${compact ? styles.compact : ""}`} aria-label={`${title}: planned`}>
      <div className={styles.head}>
        <span className={styles.when}>
          <span className={styles.dot} aria-hidden="true" />
          {s.name} · {s.window}
        </span>
        <h2 className={styles.title}>{title}</h2>
      </div>
      {children ? <div className={styles.body}>{children}</div> : null}
      {items.length ? (
        <ul className={styles.items}>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {endpoints.length ? (
        <div className={styles.api}>
          <span className={styles.apiLabel}>API ready today</span>
          <ul>
            {endpoints.map((e) => (
              <li key={e}>
                <code>{e}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
