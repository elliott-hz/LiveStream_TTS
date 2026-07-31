import { useState } from "react";
import DashboardPage from "./pages/DashboardPage";
import ProductPage from "./pages/ProductPage";
import VideoAssetPage from "./pages/VideoAssetPage";
import LiveVideoPage from "./pages/LiveVideoPage";
import LiveRoomPage from "./pages/LiveRoomPage";
import LiveControlPage from "./pages/LiveControlPage";
import InteractionPage from "./pages/InteractionPage";
import AccountPage from "./pages/AccountPage";
import PlatformPage from "./pages/PlatformPage";
import SettingsPage from "./pages/SettingsPage";
import MerchantPage from "./pages/MerchantPage";

// ---- 页面类型 ----
type Page =
  | "liveBoard" | "productMaterial" | "productLive"
  | "products" | "split" | "videos"
  | "rooms" | "live" | "interact"
  | "account" | "platform" | "settings"
  | "merchant";

const PAGE_TITLES: Record<Page, string> = {
  liveBoard: "📡 直播数据看板", productMaterial: "🎞️ 商品素材数据", productLive: "📡 商品直播数据",
  products: "🛒 商品知识库", split: "🎞️ 视频素材库", videos: "🎬 直播视频库",
  rooms: "🏠 直播间管理", live: "📡 直播中控台", interact: "💬 互动设置",
  account: "👥 账号管理", platform: "🔗 平台接入", settings: "⚙️ 系统设置",
  merchant: "🏪 商户信息",
};

const ICON: Record<Page, string> = {
  liveBoard: "📡", productMaterial: "🎞️", productLive: "📡",
  products: "🛒", split: "🎞️", videos: "🎬",
  rooms: "🏠", live: "📡", interact: "💬",
  account: "👥", platform: "🔗", settings: "⚙️",
  merchant: "🏪",
};

export default function App() {
  const [page, setPage] = useState<Page>("live");

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <Sidebar page={page} onNav={setPage} />
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <TopBar title={PAGE_TITLES[page]} />
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          <PageContent page={page} />
        </div>
      </main>
    </div>
  );
}

// ==================== Sidebar ====================

function Sidebar({ page, onNav }: { page: Page; onNav: (p: Page) => void }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">🎬 <span>AI</span> 直播工具</div>
      <div className="sidebar-subtitle">轻量级电商直播 SaaS</div>
      <nav className="sidebar-nav">
        <NavSection title="数据大盘" />
        <NavItem page="liveBoard" label="直播数据看板" current={page} onClick={onNav} />
        <NavItem page="productMaterial" label="商品素材数据" current={page} onClick={onNav} />
        <NavItem page="productLive" label="商品直播数据" current={page} onClick={onNav} />

        <NavSection title="内容管理" />
        <NavItem page="products" label="商品知识库" current={page} onClick={onNav} />
        <NavItem page="split" label="视频素材库" current={page} onClick={onNav} />
        <NavItem page="videos" label="直播视频库" current={page} onClick={onNav} />

        <NavSection title="直播运营" />
        <NavItem page="rooms" label="直播间管理" current={page} onClick={onNav} />
        <NavItem page="live" label="直播中控台" current={page} onClick={onNav} badge="LIVE" />
        <NavItem page="interact" label="互动设置" current={page} onClick={onNav} />

        <NavSection title="平台设置" />
        <NavItem page="account" label="账号管理" current={page} onClick={onNav} />
        <NavItem page="platform" label="平台接入" current={page} onClick={onNav} />
        <NavItem page="settings" label="系统设置" current={page} onClick={onNav} />
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-user" onClick={() => onNav("merchant")} title="点击查看商户信息">
          <div className="avatar">张</div>
          <div className="info">
            <div className="name">张老板的店铺</div>
            <div className="role">专业版 · 剩余 187 天</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavSection({ title }: { title: string }) {
  return <div className="nav-section">{title}</div>;
}

function NavItem({ page, label, current, onClick, badge }: {
  page: Page; label: string; current: Page; onClick: (p: Page) => void; badge?: string;
}) {
  const active = page === current;
  return (
    <div className={`nav-item ${active ? "active" : ""}`} onClick={() => onClick(page)}>
      <span className="icon">{ICON[page]}</span>
      {label}
      {badge && <span className="nav-badge">{badge}</span>}
    </div>
  );
}

// ==================== TopBar ====================

function TopBar({ title }: { title: string }) {
  return (
    <div className="topbar">
      <h2>{title}</h2>
      <div className="topbar-actions">
        <div className="status-dot" />
        <span className="status-text">系统运行中</span>
      </div>
    </div>
  );
}

// ==================== Page Router ====================

function PageContent({ page }: { page: Page }) {
  switch (page) {
    // 数据大盘 (合并在一个组件里，Tab 切换)
    case "liveBoard":
    case "productMaterial":
    case "productLive":
      return <DashboardPage tab={page} />;

    // 内容管理
    case "products": return <ProductPage />;
    case "split":    return <VideoAssetPage />;
    case "videos":   return <LiveVideoPage />;

    // 直播运营
    case "rooms":    return <LiveRoomPage />;
    case "live":     return <LiveControlPage />;
    case "interact": return <InteractionPage />;

    // 平台设置
    case "account":  return <AccountPage />;
    case "platform": return <PlatformPage />;
    case "settings": return <SettingsPage />;

    // 商户信息
    case "merchant": return <MerchantPage />;

    default: return null;
  }
}
