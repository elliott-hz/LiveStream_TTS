import { useState, useEffect } from "react";
import { liveVideosApi, LiveVideoOut } from "../api/endpoints";
import { useApi } from "../hooks/useApi";

export default function LiveVideoPage() {
  const { data: videos, refresh } = useApi(() => liveVideosApi.list(), []);
  const [selected, setSelected] = useState<LiveVideoOut | null>(null);

  const handleCreate = async () => {
    const name = prompt("编排名称:");
    if (!name) return;
    await liveVideosApi.create({ name });
    refresh();
  };

  const handleAddClip = async () => {
    if (!selected) return;
    const segmentId = prompt("切片ID:") || "";
    if (!segmentId) return;
    await liveVideosApi.addClip(selected.id, { segment_id: segmentId, sort_order: selected.clips.length, weight: 1, pause_after: 0 });
    const updated = await liveVideosApi.list();
    setSelected(updated.find(v => v.id === selected.id) || null);
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <button className="btn-primary" onClick={handleCreate}>+ 新建编排</button>
      </div>

      <div className="grid-2">
        {videos?.map(v => (
          <div className="card" key={v.id} onClick={() => setSelected(v)} style={{ cursor: "pointer" }}>
            <div className="card-header">
              <h3>🎬 {v.name}</h3>
              <span className="tag tag-primary">{v.play_mode === "sequential" ? "顺序播放" : "随机播放"}</span>
            </div>
            <div className="card-body">
              <div className="text-muted">{v.clips.length} 个切片</div>
              {v.clips.map((c, i) => (
                <div key={c.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                  #{c.sort_order + 1} · 切片 {c.segment_id} · 权重 {c.weight} · 停顿 {c.pause_after}s
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Detail */}
      {selected && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h3>📝 {selected.name} — 编排详情</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-outline btn-sm" onClick={handleAddClip}>+ 添加切片</button>
              <button className="btn-outline btn-sm" onClick={() => setSelected(null)}>关闭</button>
            </div>
          </div>
          <div className="card-body">
            <table>
              <thead><tr><th>#</th><th>切片ID</th><th>权重</th><th>停顿(s)</th><th>特写</th><th>转场</th><th>操作</th></tr></thead>
              <tbody>
                {selected.clips.map((c, i) => (
                  <tr key={c.id}>
                    <td>{c.sort_order + 1}</td><td>{c.segment_id}</td><td>{c.weight}</td><td>{c.pause_after}</td>
                    <td>—</td><td>—</td>
                    <td>
                      <button className="btn-outline btn-xs" onClick={async () => {
                        await liveVideosApi.removeClip(selected.id, c.id);
                        const updated = await liveVideosApi.list();
                        setSelected(updated.find(v => v.id === selected.id) || null);
                      }}>移除</button>
                    </td>
                  </tr>
                ))}
                {selected.clips.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: "center", padding: 20 }}>暂无切片，点击上方添加</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
