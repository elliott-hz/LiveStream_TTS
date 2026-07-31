import { useApi } from "../hooks/useApi";
import { accountApi } from "../api/endpoints";
import StatCard from "../components/StatCard";

export default function MerchantPage() {
  const { data: merchant } = useApi(() => accountApi.getMerchant(), []);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <div style={{ width: 64, height: 64, background: "var(--primary)", borderRadius: "50%",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, color: "#fff", fontWeight: 700 }}>张</div>
        <div>
          <h2 style={{ fontSize: 20 }}>{merchant?.name || "张老板的店铺"}</h2>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>商户ID: {merchant?.id || "—"} · 注册日期: 2026-01-24</div>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="📦 当前套餐" value={merchant?.tier === "pro" ? "专业版" : merchant?.tier || "—"} sub="¥999/月" />
        <StatCard label="📅 到期日期" value="2027-01-24" sub="剩余 187 天" />
        <StatCard label="🏠 直播间配额" value={`2 / ${merchant?.max_rooms || 10}`} />
        <StatCard label="📡 并发推流配额" value={`1 / ${merchant?.max_streams || 5}`} />
      </div>

      <div className="card">
        <div className="card-header"><h3>📋 基本信息</h3></div>
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
            <div><span style={{ color: "var(--text-muted)" }}>联系人：</span>张三</div>
            <div><span style={{ color: "var(--text-muted)" }}>手机号：</span>138****8888</div>
            <div><span style={{ color: "var(--text-muted)" }}>邮箱：</span>zhang@example.com</div>
            <div><span style={{ color: "var(--text-muted)" }}>已接入平台：</span>淘宝</div>
            <div><span style={{ color: "var(--text-muted)" }}>本月开播时长：</span>124 小时</div>
            <div><span style={{ color: "var(--text-muted)" }}>累计弹幕互动：</span>12,847 条</div>
          </div>
        </div>
      </div>
    </div>
  );
}
