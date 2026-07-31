export default function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value" style={{ fontSize: value.length > 10 ? 20 : 28 }}>{value}</div>
      {sub && <div className={`change ${sub.includes("↑") ? "up" : sub.includes("↓") ? "down" : ""}`}>{sub}</div>}
    </div>
  );
}
