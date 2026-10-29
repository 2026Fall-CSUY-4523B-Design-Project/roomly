// A labeled input whose error (from ApiError.fields) sits right under it.
export default function Field({ id, label, error, hint, ...input }) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={id}
        className="input"
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...input}
      />
      {error ? (
        <span id={`${id}-error`} className="error-text">
          {error}
        </span>
      ) : hint ? (
        <span id={`${id}-hint`} className="hint">
          {hint}
        </span>
      ) : null}
    </div>
  );
}
