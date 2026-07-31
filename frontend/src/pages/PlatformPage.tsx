import { platformApi } from "../api/endpoints";
import { useApi } from "../hooks/useApi";

const CAP_NAMES: Record<string, string> = { stream: "推流", danmaku: "弹幕", product_pop: "弹品", reply: "回复" };

export default function PlatformPage() {
  const { data: caps } = useApi(() => platformApi.getCapabilities(), []);

  return (
    <div>
      <div className="text-muted" style={{ marginBottom: 20 }}>
        管理各直播平台的 API 接入与推流配置。API 凭证所有直播间共用，RTMP 推流地址在"直播间管理"中单独配置。
      </div>

      {/* 已接入 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>✅ 已接入平台</h3></div>
        <div className="card-body">
          {caps?.filter((c: any) => c.is_connected).length === 0
            ? <p className="text-muted">暂无已接入平台</p>
            : caps?.filter((c: any) => c.is_connected).map((c: any) => (
                <div key={c.platform} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                  {c.icon} {c.name} — 已授权
                </div>))
          }
        </div>
      </div>

      {/* 可接入 */}
      <div className="card">
        <div className="card-header"><h3>⭐ 可接入平台</h3></div>
        <div className="card-body">
          <table>
            <thead><tr><th>平台</th><th>支持能力</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {caps?.map((c: any) => {
                const capCount = Object.values(c.capabilities).filter(Boolean).length;
                return (
                  <tr key={c.platform}>
                    <td><strong>{c.icon} {c.name}</strong></td>
                    <td>
                      {Object.entries(c.capabilities).map(([k, v]) =>
                        <span key={k} className={`tag ${v ? "tag-success" : "tag-neutral"}`} style={{ marginRight: 4 }}>
                          {CAP_NAMES[k] || k}
                        </span>
                      )}
                      <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 4 }}>{capCount}/4</span>
                    </td>
                    <td>{c.is_connected ? "🟢 已接入" : "⚪ 未接入"}</td>
                    <td>
                      <button className={c.is_connected ? "btn-outline btn-sm" : "btn-primary btn-sm"}
                        onClick={async () => {
                          if (c.is_connected) {
                            const key = prompt("API Key:") || "";
                            await platformApi.upsertConfig(c.platform, { app_key: key });
                          } else {
                            alert(`接入 ${c.name}: 填写 AppKey/AppSecret → 验证 → 激活`);
                          }
                        }}>
                        {c.is_connected ? "配置" : "接入"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{ marginTop: 16, padding: "10px 14px", background: "#f8fafc", borderRadius: 6, fontSize: 12, color: "var(--text-muted)" }}>
            📌 <strong>视频号、小红书、唯品会</strong>目前仅支持 RTMP 推流，暂缓接入。
          </div>
        </div>
      </div>
    </div>
  );
}
