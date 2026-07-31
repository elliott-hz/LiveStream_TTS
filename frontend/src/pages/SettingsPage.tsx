import { settingsApi } from "../api/endpoints";
import { useApi } from "../hooks/useApi";

export default function SettingsPage() {
  const { data: settings, refresh } = useApi(() => settingsApi.list(), []);

  return (
    <div className="card">
      <div className="card-header"><h3>⚙️ 全局设置</h3></div>
      <div className="card-body">
        {settings?.map((s: any) => (
          <div key={s.key} style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: 12, background: "#f8fafc", borderRadius: 6, marginBottom: 8
          }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{s.description || s.key}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>{s.key}</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input defaultValue={s.value} id={`setting-${s.key}`}
                style={{ padding: "6px 10px", border: "1px solid var(--border)", borderRadius: 6, fontSize: 13, width: 120 }} />
              <button className="btn-primary btn-sm" onClick={async () => {
                const val = (document.getElementById(`setting-${s.key}`) as HTMLInputElement).value;
                await settingsApi.update(s.key, val);
                refresh();
              }}>保存</button>
            </div>
          </div>
        ))}
        {(!settings || settings.length === 0) && <p className="text-muted">暂无设置项</p>}
      </div>
    </div>
  );
}
