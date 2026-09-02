export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div className="row-list" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div className="row" key={index} style={{ gap: 14 }}>
          <span className="skeleton" style={{ width: 34, height: 34, borderRadius: "var(--r-sm)" }} />
          <span style={{ flex: 1, display: "grid", gap: 8 }}>
            <span className="skeleton" style={{ height: 14, width: "40%" }} />
            <span className="skeleton" style={{ height: 11, width: "65%" }} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function SkeletonPage({ withForm = true }: { withForm?: boolean }) {
  return (
    <div className="app-content wide">
      <div className="section-heading">
        <div style={{ display: "grid", gap: 8 }}>
          <span className="skeleton" style={{ height: 11, width: 120 }} />
          <span className="skeleton" style={{ height: 30, width: 260 }} />
        </div>
      </div>
      {withForm ? (
        <div className="skeleton" style={{ height: 76, borderRadius: "var(--r-lg)", marginBottom: 28 }} />
      ) : null}
      <SkeletonRows />
    </div>
  );
}
