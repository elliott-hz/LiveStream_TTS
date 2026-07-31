import { useState } from "react";

type Tab = "liveBoard" | "productMaterial" | "productLive";

export default function DashboardPage({ tab: initialTab }: { tab: string }) {
  const [tab, setTab] = useState<Tab>((initialTab as Tab) || "liveBoard");

  return (
    <div>
      <div className="tabs">
        <div className={`tab ${tab === "liveBoard" ? "active" : ""}`} onClick={() => setTab("liveBoard")}>
          📡 直播数据看板
        </div>
        <div className={`tab ${tab === "productMaterial" ? "active" : ""}`} onClick={() => setTab("productMaterial")}>
          🎞️ 商品素材数据
        </div>
        <div className={`tab ${tab === "productLive" ? "active" : ""}`} onClick={() => setTab("productLive")}>
          📡 商品直播数据
        </div>
      </div>

      {tab === "liveBoard" && <LiveBoard />}
      {tab === "productMaterial" && <ProductMaterial />}
      {tab === "productLive" && <ProductLive />}
    </div>
  );
}

function LiveBoard() {
  return (
    <div>
      <div className="form-group">
        <label>选择场次</label>
        <select defaultValue="S001">
          <option value="S001">✅ 夏季女装专场（淘宝）| 2026-07-22 08:00 | 12h 34m</option>
          <option value="S002">✅ 夏季女装专场（淘宝）| 2026-07-21 08:00 | 10h 30m</option>
          <option value="S003">✅ 美妆护肤专场（淘宝）| 2026-07-20 14:00 | 6h 00m</option>
        </select>
      </div>

      <div className="stats-grid">
        <StatCard label="直播时长" value="12h 34m" sub="" />
        <StatCard label="累计观看" value="3,427" sub="峰值 892" />
        <StatCard label="弹幕总数" value="486" sub="AI回复率 78%" />
        <StatCard label="新增粉丝" value="47" sub="+12% ↑" />
        <StatCard label="商品弹窗" value="48 次" sub="点击率 23%" />
        <StatCard label="成交订单" value="32 单" sub="¥5,280" />
        <StatCard label="点赞数" value="2,156" sub="" />
        <StatCard label="礼物收入" value="¥128" sub="" />
      </div>

      <div className="card">
        <div className="card-header"><h3>商品讲解表现</h3></div>
        <div className="card-body">
          <table>
            <thead><tr><th>商品</th><th>讲解时长</th><th>弹窗次数</th><th>弹幕提及</th><th>点击率</th></tr></thead>
            <tbody>
              <tr><td>法式碎花连衣裙</td><td>180min</td><td>24</td><td>156</td><td>28%</td></tr>
              <tr><td>冰丝防晒袖套</td><td>90min</td><td>12</td><td>89</td><td>19%</td></tr>
              <tr><td>草编遮阳帽</td><td>60min</td><td>8</td><td>52</td><td>15%</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ProductMaterial() {
  const data = [
    { id: "D001", name: "法式碎花连衣裙", category: "女装", materialCount: 2, clipCount: 3, duration: "47min", coverage: 54 },
    { id: "D002", name: "冰丝防晒袖套", category: "配饰", materialCount: 1, clipCount: 1, duration: "12min", coverage: 14 },
    { id: "D003", name: "草编遮阳帽", category: "配饰", materialCount: 1, clipCount: 1, duration: "17min", coverage: 20 },
    { id: "D004", name: "纯棉基础款T恤", category: "女装", materialCount: 1, clipCount: 1, duration: "5min", coverage: 6 },
    { id: "D005", name: "冰丝休闲短裤", category: "女装", materialCount: 1, clipCount: 1, duration: "6min", coverage: 7 },
    { id: "D006", name: "轻便运动鞋", category: "鞋靴", materialCount: 0, clipCount: 0, duration: "—", coverage: 0 },
  ];

  return (
    <div className="card">
      <div className="card-header"><h3>商品素材关联表</h3></div>
      <div className="card-body">
        <table>
          <thead><tr><th>商品</th><th>SKU</th><th>分类</th><th>素材数</th><th>切片数</th><th>总时长</th><th>覆盖率</th><th>操作</th></tr></thead>
          <tbody>
            {data.map(p => (
              <tr key={p.id}>
                <td><strong>{p.name}</strong></td>
                <td>{p.id}</td>
                <td><span className="tag tag-neutral">{p.category}</span></td>
                <td style={{ textAlign: "center" }}>{p.materialCount} 个</td>
                <td style={{ textAlign: "center" }}>{p.clipCount} 个</td>
                <td>{p.duration}</td>
                <td style={{ minWidth: 100 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div className="progress-bar" style={{ flex: 1 }}>
                      <div className="fill fill-primary" style={{ width: `${p.coverage}%` }} />
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 600 }}>{p.coverage}%</span>
                  </div>
                </td>
                <td>
                  {p.coverage === 0
                    ? <button className="btn-primary btn-sm">📤 上传素材</button>
                    : <button className="btn-outline btn-sm">查看切片</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProductLive() {
  const data = [
    { id: "D001", name: "法式碎花连衣裙", category: "女装", roomCount: 2, playCount: 48, duration: "720min", danmaku: 156, popup: 48 },
    { id: "D002", name: "冰丝防晒袖套", category: "配饰", roomCount: 1, playCount: 24, duration: "288min", danmaku: 89, popup: 24 },
    { id: "D003", name: "草编遮阳帽", category: "配饰", roomCount: 1, playCount: 18, duration: "306min", danmaku: 52, popup: 18 },
    { id: "D006", name: "轻便运动鞋", category: "鞋靴", roomCount: 0, playCount: 0, duration: "—", danmaku: 0, popup: 0 },
  ];

  return (
    <div className="card">
      <div className="card-header"><h3>商品直播关联表</h3></div>
      <div className="card-body">
        <table>
          <thead><tr><th>商品</th><th>SKU</th><th>分类</th><th>直播间数</th><th>播放次数</th><th>播放时长</th><th>弹幕提及</th><th>弹品次数</th><th>操作</th></tr></thead>
          <tbody>
            {data.map(p => (
              <tr key={p.id}>
                <td><strong>{p.name}</strong></td>
                <td>{p.id}</td>
                <td><span className="tag tag-neutral">{p.category}</span></td>
                <td style={{ textAlign: "center" }}>{p.roomCount} 个</td>
                <td style={{ textAlign: "center" }}>{p.playCount} 次</td>
                <td>{p.duration}</td>
                <td>{p.danmaku} 次</td>
                <td>{p.popup} 次</td>
                <td>
                  {p.roomCount === 0
                    ? <button className="btn-outline btn-sm">加入排班</button>
                    : <button className="btn-outline btn-sm">互动详情</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className={`change ${sub.includes("↑") ? "up" : ""}`}>{sub}</div>}
    </div>
  );
}
