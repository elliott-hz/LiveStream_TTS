import { useState, useEffect, useRef } from "react";
import { roomsApi } from "../api/endpoints";

const API_HOST = window.location.host;

export default function LiveControlPage() {
  const [roomId, setRoomId] = useState("");
  const [status, setStatus] = useState("disconnected");
  const [danmakus, setDanmakus] = useState<{ user: string; content: string; time: string }[]>([]);
  const [metrics, setMetrics] = useState({ viewers: 0, danmaku_total: 0, pops: 0, orders: 0 });
  const [rooms, setRooms] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    roomsApi.list().then(setRooms);
  }, []);

  const connect = (rid: string) => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(`ws://${API_HOST}/ws/live/${rid}`);
    wsRef.current = ws;
    setRoomId(rid);
    setStatus("connecting");

    ws.onopen = () => setStatus("connected");
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "danmaku") setDanmakus(prev => [...prev.slice(-49), msg]);
      if (msg.type === "metrics") setMetrics(msg);
      if (msg.type === "ai_reply") setDanmakus(prev => [...prev.slice(-49), { user: "AI", content: msg.content, time: "" }]);
    };
    ws.onclose = () => setStatus("disconnected");
  };

  const send = (msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(msg));
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "320px 1fr 320px", gap: 16, height: "calc(100vh - 120px)" }}>
      {/* 左侧：弹幕面板 */}
      <div style={{ background: "var(--card-bg)", borderRadius: "var(--radius)", padding: 16, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <h3 style={{ fontSize: 15, marginBottom: 12 }}>💬 实时弹幕</h3>
        <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
          <select onChange={e => connect(e.target.value)} style={{ flex: 1, padding: 6, borderRadius: 6, border: "1px solid var(--border)" }}>
            <option value="">选择直播间</option>
            {rooms.map(r => <option key={r.id} value={r.id}>{r.name} ({r.status === "live" ? "●" : "○"})</option>)}
          </select>
          <span className={`tag ${status === "connected" ? "tag-success" : "tag-neutral"}`}>{status}</span>
        </div>
        <div style={{ flex: 1, overflow: "auto", fontSize: 13 }}>
          {danmakus.map((d, i) => (
            <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <span style={{ fontWeight: 600, color: d.user === "AI" ? "var(--primary)" : "var(--text)" }}>{d.user}</span>
              <span style={{ color: "var(--text-muted)", fontSize: 11, marginLeft: 8 }}>{d.time}</span>
              <div>{d.content}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 中间：直播画面 */}
      <div style={{ background: "#1e293b", borderRadius: "var(--radius)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative", overflow: "hidden" }}>
        <div style={{ color: "#fff", fontSize: 24, opacity: .3 }}>🎬 直播画面</div>
        <div style={{ position: "absolute", top: 12, left: 12, background: "var(--danger)", color: "#fff", padding: "4px 10px", borderRadius: 4, fontSize: 12, fontWeight: 700 }}>LIVE</div>
        <div style={{ position: "absolute", top: 12, right: 12, color: "#fff", fontSize: 12 }}>👁 {metrics.viewers}</div>
      </div>

      {/* 右侧：操作面板 */}
      <div style={{ background: "var(--card-bg)", borderRadius: "var(--radius)", padding: 16, display: "flex", flexDirection: "column" }}>
        <h3 style={{ fontSize: 15, marginBottom: 12 }}>🎛️ 运营操作</h3>
        <div className="stats-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <StatCard label="观看人数" value={String(metrics.viewers)} />
          <StatCard label="弹幕数" value={String(metrics.danmaku_total)} />
          <StatCard label="弹窗次数" value={String(metrics.pops)} />
          <StatCard label="订单金额" value={String(metrics.orders)} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
          <button className="btn-primary" onClick={() => send({ type: "pop_product", product_id: "D001" })}>🛒 手动弹品</button>
          <button className="btn-outline" onClick={() => send({ type: "switch_product" })}>⏭ 切品</button>
          <button className="btn-outline" onClick={() => send({ type: "manual_reply", content: "感谢关注~" })}>💬 人工回复</button>
          <button className="btn-danger" onClick={() => { if (confirm("确认紧急关停?")) send({ type: "emergency_stop" }); }}>
            🚨 紧急关停
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card" style={{ padding: 12 }}>
      <div className="label" style={{ fontSize: 11 }}>{label}</div>
      <div className="value" style={{ fontSize: 20 }}>{value}</div>
    </div>
  );
}
