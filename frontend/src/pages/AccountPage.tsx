import { useState } from "react";
import { accountApi } from "../api/endpoints";
import { useApi } from "../hooks/useApi";
import StatCard from "../components/StatCard";

export default function AccountPage() {
  const { data: merchant } = useApi(() => accountApi.getMerchant(), []);
  const { data: users, refresh } = useApi(() => accountApi.listUsers(), []);

  return (
    <div>
      <div className="stats-grid">
        <StatCard label="主账号" value={merchant?.name || "—"} sub={`套餐: ${merchant?.tier || "—"}`} />
        <StatCard label="子账号数" value={String(users?.length || 0)} sub="共享主账号时长" />
        <StatCard label="本月已用时长" value="124h" sub={`${users?.length || 0} 个子账号活跃`} />
        <StatCard label="到期提醒" value="187 天后" sub="2027-01-24" />
      </div>

      <div className="card">
        <div className="card-header">
          <h3>👥 子账号管理</h3>
          <button className="btn-primary btn-sm" onClick={async () => {
            const name = prompt("子账号用户名:");
            if (!name) return;
            await accountApi.createUser({ username: name, role: "editor" });
            refresh();
          }}>+ 创建子账号</button>
        </div>
        <div className="card-body">
          <table>
            <thead><tr><th>用户名</th><th>角色</th><th>时长模式</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {users?.map((u: any) => (
                <tr key={u.id}>
                  <td><strong>{u.username}</strong></td>
                  <td><span className="tag tag-primary">{u.role}</span></td>
                  <td>{u.quota_hours ? `${u.quota_hours}h 独立` : "共享主账号"}</td>
                  <td><span className="tag tag-success">活跃</span></td>
                  <td>
                    <button className="btn-outline btn-xs" onClick={async () => {
                      if (confirm("确认删除?")) { await accountApi.deleteUser(u.id); refresh(); }
                    }}>删除</button>
                  </td>
                </tr>
              ))}
              {(!users || users.length === 0) && (
                <tr><td colSpan={5} style={{ textAlign: "center", padding: 20 }}>暂无子账号</td></tr>
              )}
            </tbody>
          </table>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button className="btn-outline btn-sm">📥 下载使用明细</button>
            <button className="btn-outline btn-sm">💰 续费</button>
          </div>
        </div>
      </div>
    </div>
  );
}
