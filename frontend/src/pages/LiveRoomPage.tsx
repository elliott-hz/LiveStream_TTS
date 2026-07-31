import { useState } from "react";
import { roomsApi, liveVideosApi, RoomOut, LiveVideoOut } from "../api/endpoints";
import { useApi } from "../hooks/useApi";
import Modal from "../components/Modal";
import StatCard from "../components/StatCard";

export default function LiveRoomPage() {
  const { data: rooms, refresh } = useApi(() => roomsApi.list(), []);
  const { data: liveVideos } = useApi(() => liveVideosApi.list(), []);
  const [createOpen, setCreateOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState<string | null>(null);

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn-primary" onClick={() => setCreateOpen(true)}>+ 创建直播间</button>
        <span className="text-muted">
          已用 {rooms?.filter(r => r.status === "live").length || 0} / {rooms?.length || 0} 路
        </span>
      </div>

      <div className="grid-2">
        {rooms?.map(r => {
          const isLive = r.status === "live";
          return (
            <div className="card" key={r.id} style={{ borderLeft: isLive ? "3px solid var(--success)" : undefined }}>
              <div className="card-header">
                <h3>🏠 {r.name}</h3>
                <span className={`tag ${isLive ? "tag-success" : "tag-neutral"}`}>
                  {isLive ? "● 推流中" : "○ 待开播"}
                </span>
              </div>
              <div className="card-body">
                <div className="text-muted" style={{ marginBottom: 8 }}>
                  {r.platform} · RTMP: <code>{r.rtmp_url.substring(0, 30)}...</code>
                </div>
                {r.attached_video_id
                  ? <span className="tag tag-primary">已挂载视频</span>
                  : <span className="tag tag-warning">未挂载视频</span>}
                <div style={{ marginTop: 12, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {isLive ? (
                    <button className="btn-danger btn-sm" onClick={async () => { await roomsApi.stop(r.id); refresh(); }}>⏹ 停播</button>
                  ) : (
                    <>
                      <button className="btn-primary btn-sm" disabled={!r.attached_video_id}
                        onClick={async () => { await roomsApi.start(r.id); refresh(); }}>▶ 开播</button>
                      <button className="btn-outline btn-sm" onClick={() => setScheduleOpen(r.id)}>🕐 排班</button>
                      <button className="btn-outline btn-sm" onClick={async () => {
                        const vid = prompt("挂载直播视频ID:") || "";
                        if (vid) { await roomsApi.attach(r.id, vid); refresh(); }
                      }}>📎 挂载视频</button>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="📝 创建直播间"
        footer={<><button className="btn-outline" onClick={() => setCreateOpen(false)}>取消</button>
          <button className="btn-primary" onClick={async () => {
            const name = (document.getElementById("rName") as HTMLInputElement).value;
            const rtmp = (document.getElementById("rRtmp") as HTMLInputElement).value;
            if (name && rtmp) { await roomsApi.create({ name, platform: "taobao", rtmp_url: rtmp }); setCreateOpen(false); refresh(); }
          }}>创建</button></>}>
        <div className="form-group"><label>直播间名称</label><input id="rName" placeholder="例：夏季女装专场" /></div>
        <div className="form-group">
          <label>平台</label><select><option>淘宝</option><option>抖音</option><option>快手</option></select>
        </div>
        <div className="form-group">
          <label>RTMP 推流地址</label>
          <input id="rRtmp" placeholder="rtmp://push.xxx.com/live/..." />
          <div className="text-muted" style={{ marginTop: 4 }}>从平台直播后台复制推流地址</div>
        </div>
      </Modal>

      {/* Schedule Modal */}
      <Modal open={!!scheduleOpen} onClose={() => setScheduleOpen(null)} title="🕐 定时排班"
        footer={<><button className="btn-outline" onClick={() => setScheduleOpen(null)}>取消</button>
          <button className="btn-primary" onClick={async () => {
            if (!scheduleOpen) return;
            const enabled = (document.getElementById("sEnabled") as HTMLInputElement).checked;
            const start = (document.getElementById("sStart") as HTMLInputElement).value;
            const end = (document.getElementById("sEnd") as HTMLInputElement).value;
            await roomsApi.setSchedule(scheduleOpen, { enabled, start_time: start || undefined, end_time: end || undefined });
            setScheduleOpen(null);
          }}>保存</button></>}>
        <div className="form-group">
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" id="sEnabled" />启用定时开关播</label>
        </div>
        <div className="form-row">
          <div className="form-group"><label>开播时间</label><input type="time" id="sStart" defaultValue="08:00" /></div>
          <div className="form-group"><label>关播时间</label><input type="time" id="sEnd" defaultValue="22:00" /></div>
        </div>
      </Modal>
    </div>
  );
}
