import { useState } from "react";

// ---- 页面组件 (占位，后续逐步实现) ----
// 对应 Demo HTML 的 7 个商户端页面

type Page =
  | "liveBoard"
  | "productMaterial"
  | "productLive"
  | "products"
  | "split"
  | "videos"
  | "rooms"
  | "live"
  | "interact";

const PAGE_TITLES: Record<Page, string> = {
  liveBoard: "📡 直播数据看板",
  productMaterial: "🎞️ 商品素材数据",
  productLive: "📡 商品直播数据",
  products: "🛒 商品知识库",
  split: "🎞️ 视频素材库",
  videos: "🎬 直播视频库",
  rooms: "🏠 直播间管理",
  live: "📡 直播中控台",
  interact: "💬 互动设置",
};

export default function App() {
  const [page, setPage] = useState<Page>("live");

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Sidebar */}
      <aside
        style={{
          width: 240,
          background: "var(--sidebar-bg)",
          color: "var(--sidebar-text)",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
        }}
      >
        <div style={{ padding: "20px 24px 12px", fontSize: 18, fontWeight: 700, color: "#fff" }}>
          🎬 <span style={{ color: "#818cf8" }}>AI</span> 直播工具
        </div>
        <div style={{ padding: "0 24px 20px", fontSize: 12, color: "#94a3b8" }}>
          轻量级电商直播 SaaS
        </div>

        <nav style={{ flex: 1, padding: "4px 12px" }}>
          <NavSection title="数据大盘" />
          <NavItem page="liveBoard" icon="📡" label="直播数据看板" current={page} onClick={setPage} />
          <NavItem page="productMaterial" icon="🎞️" label="商品素材数据" current={page} onClick={setPage} />
          <NavItem page="productLive" icon="📡" label="商品直播数据" current={page} onClick={setPage} />

          <NavSection title="内容管理" />
          <NavItem page="products" icon="🛒" label="商品知识库" current={page} onClick={setPage} />
          <NavItem page="split" icon="🎞️" label="视频素材库" current={page} onClick={setPage} />
          <NavItem page="videos" icon="🎬" label="直播视频库" current={page} onClick={setPage} />

          <NavSection title="直播运营" />
          <NavItem page="rooms" icon="🏠" label="直播间管理" current={page} onClick={setPage} />
          <NavItem page="live" icon="📡" label="直播中控台" current={page} onClick={setPage} badge="LIVE" />
          <NavItem page="interact" icon="💬" label="互动设置" current={page} onClick={setPage} />
        </nav>

        <div
          style={{
            padding: 12,
            borderTop: "1px solid rgba(255,255,255,.08)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              background: "var(--primary)",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              color: "#fff",
              fontWeight: 600,
            }}
          >
            张
          </div>
          <div>
            <div style={{ color: "#fff", fontWeight: 500, fontSize: 13 }}>张老板的店铺</div>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>专业版</div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <TopBar title={PAGE_TITLES[page]} />
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          <PageContent page={page} />
        </div>
      </main>
    </div>
  );
}

// ---- 子组件 ----

function NavSection({ title }: { title: string }) {
  return (
    <div
      style={{
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 1,
        color: "#94a3b8",
        padding: "16px 12px 8px",
      }}
    >
      {title}
    </div>
  );
}

function NavItem({
  page,
  icon,
  label,
  current,
  onClick,
  badge,
}: {
  page: Page;
  icon: string;
  label: string;
  current: Page;
  onClick: (p: Page) => void;
  badge?: string;
}) {
  const active = page === current;
  return (
    <div
      onClick={() => onClick(page)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 12px",
        borderRadius: 8,
        cursor: "pointer",
        fontSize: 14,
        marginBottom: 2,
        background: active ? "var(--primary)" : "transparent",
        color: active ? "#fff" : undefined,
        fontWeight: active ? 500 : undefined,
      }}
    >
      <span style={{ fontSize: 18, width: 22, textAlign: "center" }}>{icon}</span>
      {label}
      {badge && (
        <span
          style={{
            marginLeft: "auto",
            background: "var(--danger)",
            color: "#fff",
            fontSize: 11,
            padding: "2px 7px",
            borderRadius: 10,
            fontWeight: 600,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );
}

function TopBar({ title }: { title: string }) {
  return (
    <div
      style={{
        height: 56,
        background: "var(--card-bg)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        flexShrink: 0,
      }}
    >
      <h2 style={{ fontSize: 17, fontWeight: 600 }}>{title}</h2>
    </div>
  );
}

function PageContent({ page }: { page: Page }) {
  // 各页面后端 API 调用示例
  switch (page) {
    case "products":
      return <Placeholder title="商品知识库" api="/api/products" />;
    case "split":
      return <Placeholder title="视频素材库" api="/api/video-assets" />;
    case "videos":
      return <Placeholder title="直播视频库" api="/api/live-videos" />;
    case "rooms":
      return <Placeholder title="直播间管理" api="/api/live-rooms" />;
    case "live":
      return <Placeholder title="直播中控台" api="WS /ws/live/{room_id}" />;
    case "interact":
      return <Placeholder title="互动设置" api="/api/interaction/config" />;
    case "liveBoard":
      return <Placeholder title="直播数据看板" api="/api/analytics/sessions" />;
    case "productMaterial":
      return <Placeholder title="商品素材数据" api="商品素材交叉统计" />;
    case "productLive":
      return <Placeholder title="商品直播数据" api="商品直播交叉统计" />;
    default:
      return null;
  }
}

function Placeholder({ title, api }: { title: string; api: string }) {
  return (
    <div
      style={{
        background: "var(--card-bg)",
        borderRadius: "var(--radius)",
        padding: 40,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 48, marginBottom: 16 }}>🚧</div>
      <h3 style={{ marginBottom: 8 }}>{title}</h3>
      <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
        页面开发中 · API: <code>{api}</code>
      </p>
    </div>
  );
}
