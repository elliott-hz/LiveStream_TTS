import { useState, useEffect, useRef } from "react";

interface RawVideo { id: string; file_name: string; parse_status: string; parse_progress: number; segments: Segment[]; }
interface Segment { id: string; start_time: number; end_time: number; script: string; clip_path: string; status: string; }

export default function VideoAssetPage() {
  const [videos, setVideos] = useState<RawVideo[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<RawVideo | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadVideos = async () => {
    const resp = await fetch("/api/video-assets");
    setVideos(await resp.json());
  };

  useEffect(() => { loadVideos(); }, []);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    await fetch("/api/video-assets/upload", { method: "POST", body: form });
    setUploading(false);
    setTimeout(loadVideos, 1000);
  };

  const handlePublish = async (segId: string) => {
    await fetch(`/api/video-assets/segments/${segId}/publish`, { method: "POST" });
    loadVideos();
  };

  const pollProgress = async (videoId: string) => {
    const resp = await fetch(`/api/video-assets/${videoId}`);
    const v = await resp.json();
    setSelectedVideo(v);
    if (v.parse_status === "done") loadVideos();
  };

  return (
    <div>
      {/* Upload */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>📤 上传视频</h3></div>
        <div className="card-body">
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <input type="file" ref={fileRef} accept="video/mp4" />
            <button className="btn-primary" onClick={handleUpload} disabled={uploading}>
              {uploading ? "上传中..." : "上传并解析"}
            </button>
          </div>
          <div className="text-muted" style={{ marginTop: 8 }}>支持 20min-2h 的 MP4 视频，上传后自动触发 AI 解析</div>
        </div>
      </div>

      {/* Video List */}
      <div className="grid-2">
        {videos.map(v => (
          <div className="card" key={v.id} onClick={() => { setSelectedVideo(v); pollProgress(v.id); }} style={{ cursor: "pointer" }}>
            <div className="card-header">
              <h3>🎬 {v.file_name}</h3>
              <span className={`tag ${v.parse_status === "done" ? "tag-success" : v.parse_status === "processing" ? "tag-warning" : "tag-neutral"}`}>
                {v.parse_status === "done" ? "已完成" : v.parse_status === "processing" ? "解析中" : "等待中"}
              </span>
            </div>
            <div className="card-body">
              <div className="progress-bar">
                <div className="fill fill-primary" style={{ width: `${v.parse_progress}%` }} />
              </div>
              <div className="text-muted" style={{ marginTop: 6 }}>{v.segments.length} 个切片 · 进度 {v.parse_progress}%</div>
            </div>
          </div>
        ))}
        {videos.length === 0 && (
          <div className="card"><div className="card-body" style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>暂无视频，上传一个开始解析</div></div>
        )}
      </div>

      {/* Segment Detail */}
      {selectedVideo && selectedVideo.segments.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h3>📋 切片详情 — {selectedVideo.file_name}</h3>
            <button className="btn-outline btn-sm" onClick={() => setSelectedVideo(null)}>关闭</button>
          </div>
          <div className="card-body">
            {selectedVideo.segments.map(seg => (
              <div key={seg.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 100, height: 60, background: "#f1f5f9", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>🎬</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>
                    {seg.start_time.toFixed(0)}s — {seg.end_time.toFixed(0)}s
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5, maxHeight: 36, overflow: "hidden" }}>
                    {seg.script}
                  </div>
                </div>
                <div>
                  {seg.status === "published"
                    ? <span className="tag tag-success">已发布</span>
                    : <button className="btn-primary btn-sm" onClick={() => handlePublish(seg.id)}>发布到库</button>
                  }
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
