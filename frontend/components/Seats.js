import styles from "@/styles/groups.module.css";

export const MAX_MEMBERS = 6; // R-1.2, also enforced by the database

// Six seats, filled for current members: how much room the group has left at a glance.
export default function Seats({ taken }) {
  return (
    <div className={styles.seats} role="img" aria-label={`${taken} of ${MAX_MEMBERS} seats taken`}>
      {Array.from({ length: MAX_MEMBERS }, (_, i) => (
        <span key={i} className={`${styles.seat} ${i < taken ? styles.seatTaken : ""}`} />
      ))}
    </div>
  );
}
