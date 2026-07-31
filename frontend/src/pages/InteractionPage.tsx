import { useState } from "react";
import { interactionApi, InteractionConfig } from "../api/endpoints";
import { useApi } from "../hooks/useApi";

export default function InteractionPage() {
  const { data: config, refresh } = useApi<InteractionConfig>(() => interactionApi.getConfig(), []);
  const { data: templates, refresh: refreshTemplates } = useApi(() => interactionApi.listTemplates(), []);
  const [tab, setTab] = useState<"reply" | "template" | "auto">("reply");

  return (
    <div>
      <div className="tabs">
        <div className={`tab ${tab === "reply" ? "active" : ""}`} onClick={() => setTab("reply")}>💬 回复设置</div>
        <div className={`tab ${tab === "template" ? "active" : ""}`} onClick={() => setTab("template")}>📋 话术模板</div>
        <div className={`tab ${tab === "auto" ? "active" : ""}`} onClick={() => setTab("auto")}>🤖 自动互动</div>
      </div>

      {tab === "reply" && config && (
        <div className="card">
          <div className="card-header"><h3>回复配置</h3></div>
          <div className="card-body">
            <div className="form-row">
              <div className="form-group">
                <label>回复模式</label>
                <select value={config.reply_mode} onChange={async e => {
                  await interactionApi.updateConfig({ reply_mode: e.target.value }); refresh();
                }}>
                  <option value="tts">TTS 语音驱动</option>
                  <option value="original_audio">原音频驱动</option>
                </select>
              </div>
              <div className="form-group">
                <label>回复策略</label>
                <select value={config.reply_decision} onChange={async e => {
                  await interactionApi.updateConfig({ reply_decision: e.target.value }); refresh();
                }}>
                  <option value="questions_only">仅回复提问</option>
                  <option value="all">全部弹幕</option>
                </select>
              </div>
              <div className="form-group">
                <label>回复风格</label>
                <select value={config.reply_style} onChange={async e => {
                  await interactionApi.updateConfig({ reply_style: e.target.value }); refresh();
                }}>
                  <option value="warm">亲切种草</option>
                  <option value="professional">专业讲解</option>
                  <option value="lively">激昂带货</option>
                </select>
              </div>
            </div>

            <h4 style={{ marginTop: 20, marginBottom: 12 }}>TTS 语音参数</h4>
            <div className="form-row">
              <div className="form-group">
                <label>语速: {config.tts_speed}x</label>
                <input type="range" min="0.5" max="2.0" step="0.1" value={config.tts_speed}
                  onChange={async e => {
                    await interactionApi.updateConfig({ tts_speed: parseFloat(e.target.value) }); refresh();
                  }} />
              </div>
              <div className="form-group">
                <label>音量: {Math.round(config.tts_volume * 100)}%</label>
                <input type="range" min="0" max="100" value={config.tts_volume * 100}
                  onChange={async e => {
                    await interactionApi.updateConfig({ tts_volume: parseInt(e.target.value) / 100 }); refresh();
                  }} />
              </div>
              <div className="form-group">
                <label>语调: {config.tts_pitch}x</label>
                <input type="range" min="0.5" max="2.0" step="0.1" value={config.tts_pitch}
                  onChange={async e => {
                    await interactionApi.updateConfig({ tts_pitch: parseFloat(e.target.value) }); refresh();
                  }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "template" && (
        <div className="card">
          <div className="card-header">
            <h3>话术模板</h3>
            <button className="btn-primary btn-sm" onClick={async () => {
              await interactionApi.createTemplate({ keywords: "尺码", reply_text: "亲，S-XXL都有哦~", reply_type: "voice+text" });
              refreshTemplates();
            }}>+ 添加模板</button>
          </div>
          <div className="card-body">
            <table>
              <thead><tr><th>关键词</th><th>回复内容</th><th>类型</th><th>操作</th></tr></thead>
              <tbody>
                {templates?.map((t: any) => (
                  <tr key={t.id}>
                    <td><span className="tag tag-primary">{t.keywords}</span></td>
                    <td>{t.reply_text}</td>
                    <td><span className="tag tag-neutral">{t.reply_type}</span></td>
                    <td><button className="btn-outline btn-xs" onClick={async () => {
                      await interactionApi.deleteTemplate(t.id); refreshTemplates();
                    }}>删除</button></td>
                  </tr>
                ))}
                {(!templates || templates.length === 0) && (
                  <tr><td colSpan={4} style={{ textAlign: "center", padding: 20 }}>暂无模板</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "auto" && (
        <div className="card">
          <div className="card-header"><h3>自动互动</h3></div>
          <div className="card-body">
            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" /> 进场欢迎 — 观众进入直播间时自动发送欢迎消息
              </label>
            </div>
            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" /> 关注引导 — 每 5 分钟自动发送关注引导
              </label>
            </div>
            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" /> 定时发弹幕 — 系统按间隔发送场控文案
              </label>
            </div>
            <button className="btn-outline" onClick={() => alert("模板下载中...")}>📥 下载话术模板</button>
          </div>
        </div>
      )}
    </div>
  );
}
