# Phase 2: AI 集成实施计划

> **版本:** v2.0 — 全云化方案
> **日期:** 2026-07-14
> **目标:** 5 路并发，全链路跑通，零 GPU 投入
> **策略:** AI 能力优先使用在线 API，中间件全托管，仅保留 1 台 CPU 服务器跑微服务

---

## 目录

1. [Phase 2 范围与目标](#1-phase-2-范围与目标)
2. [云服务选型](#2-云服务选型)
3. [基础设施方案](#3-基础设施方案)
4. [代码实施步骤](#4-代码实施步骤)
5. [全链路联调](#5-全链路联调)
6. [成本估算](#6-成本估算)
7. [Phase 3 升级路径](#7-phase-3-升级路径)
8. [风险与应对](#8-风险与应对)
9. [验收标准](#9-验收标准)

---

## 1. Phase 2 范围与目标

### 1.1 一句话定义

将 Phase 1 的"空壳微服务"升级为"能真正跑通的 AI 数字人直播系统"——**全程使用在线 API，零 GPU 投入**，5 个直播间同时开播。

### 1.2 Phase 2 包含

| 能力 | 对应服务 | 实现方式 | 交付物 |
|---|---|---|---|
| 语音合成 (TTS) | `tts-svc` | **阿里云 CosyVoice API** (流式) | 情感语音输出，首包 < 300ms |
| 口型渲染 | `render-svc` | **2D Viseme** (BlendShape + 音素映射, CPU) | 虚拟形象口型同步，720p@30fps |
| 直播互动 LLM | `interact-svc` | **DeepSeek API** | 弹幕回复生成，延迟 < 1s |
| NLP 语义理解 | `nlp-svc` | 0.5B 分类模型 (CPU) | 意图识别、情感分析、敏感词双模检测 |
| 知识库 RAG | `knowledge-svc` | DashVector / Milvus standalone (ECS 上) | 商品知识检索，Top5 < 100ms |
| 推流编码 | `stream-svc` | FFmpeg (CPU) | RTMP 推流到抖音/淘宝/京东 |

### 1.3 Phase 2 不包含（挪到 Phase 3）

- ❌ GPU 服务器采购
- ❌ CosyVoice2 / Wav2Lip / Qwen-3-7B 本地部署
- ❌ 新建 llm-svc（直接用 DeepSeek API）
- ❌ LoRA 微调训练管线
- ❌ 真人克隆（形象 + 音色 + 表情 + 动作）
- ❌ 3D 数字人渲染
- ❌ K8s 多节点集群

---

## 2. 云服务选型

### 2.1 TTS — 阿里云 CosyVoice API

| 项目 | 说明 |
|---|---|
| **产品** | 阿里云 智能语音交互 — CosyVoice 大模型 |
| **接口** | HTTP/WebSocket 流式，返回 PCM/MP3 |
| **情感控制** | ✅ 支持 happy/sad/excited/neutral 等标签 |
| **音色** | 20+ 预设 + 声音克隆 API |
| **价格** | ¥2/万字 |
| **5路日成本** | 按每天 1000 次回复 × 30字 ≈ 3万字 ≈ ¥6/天 |

> 备选：讯飞星火语音（¥3/万字）、腾讯云 TTS（¥1.5/万字）

### 2.2 LLM — DeepSeek API

| 项目 | 说明 |
|---|---|
| **模型** | DeepSeek-Chat (对应 DeepSeek-V2) |
| **接口** | REST API，兼容 OpenAI Chat Completions 格式 |
| **价格** | ¥1/百万 tokens |
| **5路日成本** | 每天 5000 条弹幕 × 500 tokens ≈ 250万 tokens ≈ ¥2.5/天 |

> 备选：阿里云 通义千问 Qwen-Turbo (¥0.3/百万tokens)、硅基流动 Qwen2-7B (¥0.7/百万tokens)

### 2.3 Render — 2D Viseme (自研, CPU)

Wav2Lip 没有在线 API。Phase 2 用 2D Viseme 方案替代：

```
TTS 音频 → 音素分析 (CPU) → 预渲染口型 BlendShape 切换 (CPU) → 合成画面 → FFmpeg 推流
```

| 对比 | Wav2Lip (Phase 3 上) | 2D Viseme (Phase 2) |
|---|---|---|
| GPU | 需要 L40S | **不需要** |
| 延迟 | < 80ms | < 10ms |
| 风格 | 真人级 | 虚拟形象 (2D/卡通) |
| 开发量 | 2-3 周 | 1 周 |
| 效果 | 分不出真假 | 国内电商直播主流风格 |

### 2.4 中间件 — 阿里云全托管

| 中间件 | 阿里云产品 | 按量月费 (5路规模) |
|---|---|---|
| PostgreSQL | RDS PostgreSQL (2C4G) | ¥300-500 |
| Redis | 云数据库 Redis (1GB) | ¥150-250 |
| Kafka | 消息队列 Kafka 版 (基础规格) | ¥500-800 |
| 对象存储 | OSS (100GB) | ¥20-50 |
| 向量库 | DashVector (10万向量) | ¥200-400 |
| 日志 | SLS (Simple Log Service) | ¥100-200 |
| **中间件月费合计** | | **¥1,500-2,500** |

> 开发阶段可以直接用 docker-compose 本地跑中间件，上线再切阿里云。

---

## 3. 基础设施方案

### 3.1 唯一服务器：阿里云 ECS

| 配置 | 用途 |
|---|---|
| **24C 48G** | 7 个微服务 (platform-svc 合并了11个管理服务) + FFmpeg 5路推流 + NLP 0.5B 模型 |
| **系统盘 100GB SSD** | 系统 + Docker 镜像 |
| **数据盘 200GB SSD** | 日志、临时文件 |
| **带宽 50Mbps** | 5路 RTMP 推流 (25Mbps) + API 通信 + 余量 |
| **操作系统** | Ubuntu 22.04 LTS |
| **月费** | ¥400-700 (包年 ¥4000-6000) |

### 3.2 资源分配

| 组件 | CPU | 内存 |
|---|---|---|
| 7 个微服务 (platform-svc 合并了11个管理服务) (Python) | ~4C | ~7GB |
| NLP 0.5B 推理 (CPU) | ~2C | ~2GB |
| FFmpeg 5路推流 (x264 veryfast) | ~8C | ~2GB |
| render-svc 2D Viseme | ~2C | ~2GB |
| Docker + OS overhead | ~2C | ~3GB |
| 空闲余量 | ~6C | ~32GB |
| **总计** | **24C** | **48G** |

### 3.3 架构总览

```
阿里云 ECS 24C 48G
├── gateway-svc      ─────────────────────────── 外部流量入口
├── interact-svc     ──→ DeepSeek API (LLM)      在线推理
│                       → nlp-svc (CPU, 本地)
│                       → knowledge-svc ──→ DashVector (云端)
│                       → tts-svc ────────→ 阿里云 TTS API
│                       → render-svc (2D Viseme, CPU)
│                       → stream-svc (FFmpeg RTMP)
├── user / product / script / live-mgr / avatar
│   / voice / billing / audit / analytics
│   / platform-sync / profile-svc             业务 CRUD
└── Prometheus + Grafana                       基础监控

阿里云 (外部)
├── RDS PostgreSQL     ← 所有微服务共享
├── Redis              ← 缓存 + Session
├── Kafka              ← 异步事件
├── OSS                ← 模型/素材存储
├── DashVector         ← 知识库向量检索
└── SLS                ← 日志聚合
```

---

## 4. 代码实施步骤

```
步骤 1          步骤 2          步骤 3          步骤 4          步骤 5          步骤 6
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│tts-svc   │   │nlp-svc   │   │interact  │   │knowledge │   │render-svc│   │全链路    │
│接入阿里云│ → │加载 0.5B │ → │对接      │ → │对接      │ → │2D Viseme│ → │联调      │
│TTS API   │   │分类模型  │   │DeepSeek  │   │向量检索  │   │口型渲染  │   │端到端    │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
  3-4 天          3-4 天         2-3 天         2-3 天         5-7 天         3-5 天
```

### 步骤 1: tts-svc 接入阿里云 TTS API

**当前状态:** `modules/engine/tts_engine.py` 是正弦波 mock。`config.py` 已预留 `TTS_MODEL_PATH` 和 `TTS_USE_GPU` 配置。

**改造内容:**

| 文件 | 改动 |
|---|---|
| `modules/engine/tts_engine.py` | 替换正弦波生成 → 调用阿里云 TTS WebSocket API；保持 `on_chunk/on_complete/on_error` 回调接口不变 |
| `config.py` | 新增 `TTS_BACKEND=cloud`、`TTS_API_KEY`、`TTS_API_ENDPOINT` |
| 新增 `modules/engine/cloud_tts_client.py` | 封装阿里云 TTS SDK，支持流式 PCM 回调、断线重连 |

**gRPC 接口不变** — `Synthesize` (流式) 接口照常工作，上层调用方无感知。

```
改造前: SynthesizeRequest → 正弦波生成 → SynthesizeResponse (audio chunks)
改造后: SynthesizeRequest → 阿里云TTS API → SynthesizeResponse (audio chunks)
                             ↑ 相同的回调接口
```

**验收标准:**
- 输入中文文本 → 流式输出 PCM 音频，首包 < 300ms
- `TTS_BACKEND=mock` 切换回正弦波（用于无网调试）
- 5 路并发不超 API 限流（阿里云单账号 20 QPS，够用）

### 步骤 2: nlp-svc 加载 0.5B 分类模型

**当前状态:** `interaction_service.py:355` 是关键词规则匹配 mock。

**改造内容:**

| 文件 | 改动 |
|---|---|
| `nlp-svc/src/classifiers/intent.py` | 加载 0.5B 意图分类模型（text2vec-base-chinese 或 distill-bert-chinese） |
| `nlp-svc/src/classifiers/sentiment.py` | 情感 3 分类 + 强度 |
| `nlp-svc/src/detectors/sensitive.py` | AC 自动机（毫秒级）+ 语义模型（检测变体/谐音） |

**npl-svc 本身就是 CPU 服务**，这一步不改变部署方式。

**验收标准:**
- 意图分类 P99 < 50ms
- 敏感词 AC 自动机 < 5ms，语义模型 < 100ms
- 意图准确率 > 80%（电商 12 类）

### 步骤 3: interact-svc 对接 DeepSeek API

**当前状态:** `_mock_reply()` 用关键词模板回复。

**改造内容:**

| 文件 | 改动 |
|---|---|
| `interact-svc/src/services/reply_service.py` (新增) | 封装 DeepSeek Chat API 调用、prompt 模板、多轮对话管理 |
| `interact-svc/src/pipeline/orchestrator.py` | `_mock_reply()` → `await reply_service.generate()` |
| `interact-svc/src/config.py` | 新增 `LLM_API_KEY`、`LLM_MODEL=deepseek-chat`、`LLM_API_BASE` |

**不新建 llm-svc。** 5 路并发下直接调 DeepSeek API 最划算（每天 ¥2-3），等服务规模上去了 Phase 3 再自建 llm-svc 省钱。

**Prompt 模板:**
```
[System] 你是{store_name}的AI主播{avatar_name}，性格{persona}。
         当前在播：{product_name}，价格 ¥{price}，卖点{highlights}。
         RAG知识：{rag_context}
         要求：口语化，20-50字，可带emoji。
[User] 弹幕：{danmaku_text} [意图:{intent} 情感:{sentiment}]
```

**验收标准:**
- 弹幕输入 → LLM 生成回复文本，延迟 < 1s
- API 不可用时自动降级到关键词模板（不丢弹幕）
- 支持每分钟重试 + 熔断

### 步骤 4: knowledge-svc 对接向量检索

**当前状态:** `knowledge-svc` 骨架存在。

**改造内容:**

| 文件 | 改动 |
|---|---|
| `src/services/embedding_service.py` | text2vec-base-chinese → 768 维向量 |
| `src/services/vector_store.py` | 对接 DashVector SDK (或 Milvus standalone on ECS) |

**开发阶段用 Milvus standalone**（docker-compose phase2 profile），上线切 DashVector。

**验收标准:**
- 商品知识检索 Top5 < 100ms
- 召回率 > 80%

### 步骤 5: render-svc 2D Viseme 口型渲染

**当前状态:** `renderer/lipsync.py`、`compositor.py` 骨架，输出假帧。

**改造内容 — 核心是新增 Viseme engine:**

| 文件 | 改动 |
|---|---|
| 新增 `renderer/viseme/` 目录 | 音素→口型映射表、BlendShape 控制器、12 种基础口型 PNG |
| `renderer/lipsync.py` | 改造：Wav2Lip 替换为 `VisemeEngine`，输入 TTS 音频 → 返回口型序列 |
| `renderer/compositor.py` | 虚拟形象底图 + 口型层 + 商品卡/优惠券叠加 |
| `config.py` | `RENDER_ENGINE=viseme` (默认，Phase 3 切 `wav2lip`) |

**Viseme 原理：**
```
TTS 音频 PCM → 音素分析 (phonemizer lib)
    → 每个音素映射到 12 种预定义嘴型之一
    → 根据音频能量做嘴型强度插值
    → 切换 PNG/BlendShape → 合成到数字人底图上
```

**12 种基础嘴型 (Viseme set):**
```
A / E / I / O / U / 闭嘴 / 轻微张开 / 大张开 / F-V咬唇 / L-舌尖 / M-B-P闭唇 / W-Q-圆唇
```

**验收标准:**
- TTS 音频 + 形象 ID → 720p@30fps 视频帧输出
- 口型与音频对齐（人眼感知自然即可，无需精确到 ms 级）
- 5 路并发 CPU < 40%

### 步骤 6: 全链路联调

**联调顺序:**

```
1. 基础设施: docker compose up -d (本地中间件) 或阿里云中间件连接测试
2. tts-svc 独立验证: gRPC Synthesize → 听到阿里云 TTS 语音
3. nlp-svc 独立验证: gRPC → 意图/情感/敏感词
4. DeepSeek 独立验证: interact-svc → 弹幕 → DeepSeek → 回复文本
5. knowledge 独立验证: 录入商品知识 → 检索
6. render-svc 独立验证: 音频 + 形象 → Viseme 视频帧
7. stream-svc 独立验证: 视频帧 → RTMP → VLC 播放
8. interact-svc 管线: 弹幕 → 全链路 → 画面输出
9. 5 路并发压测: 5 个直播间同时跑，监测 CPU/延迟
```

**关键延迟预算:**

| 环节 | 目标 | 累计 |
|---|---|---|
| gateway → interact | < 10ms | 10ms |
| nlp-svc 分析 | < 50ms | 60ms |
| knowledge-svc RAG | < 100ms | 160ms |
| DeepSeek API | < 800ms | 960ms |
| tts-svc (阿里云 TTS 首包) | < 300ms | 1260ms |
| render-svc Viseme | < 50ms | 1310ms |
| stream-svc 编码 | < 50ms | 1360ms |
| **端到端 (弹幕 → 画面)** | **< 1.5s** | |

---

## 5. 全链路联调

### 5.1 端到端数据流

```
抖音/淘宝 直播间
      │ 弹幕
      ▼
┌──────────────────────────────────────────────────┐
│                  ECS 24C 48G                      │
│                                                    │
│  gateway-svc → interact-svc (管线编排)             │
│                   ├──→ nlp-svc (CPU, 本地)         │
│                   ├──→ knowledge-svc → DashVector  │
│                   ├──→ DeepSeek API (互联网)       │
│                   └──→ tts-svc → 阿里云 TTS API   │
│                         ↓                          │
│                   render-svc (2D Viseme, CPU)      │
│                         ↓                          │
│                   stream-svc (FFmpeg → RTMP)       │
└──────────────────────────────────────────────────┘
      │ RTMP
      ▼
   直播平台
```

### 5.2 测试场景清单

| 场景 | 输入 | 期望输出 |
|---|---|---|
| 产品咨询 | "这个口红多少钱" | LLM 回复价格 + TTS 语音 |
| 砍价 | "便宜点行不行" | LLM 回复优惠信息 |
| 负面评论 | "质量太差了" | 敏感词检测通过，LLM 安抚回复 |
| 闲聊 | "主播好漂亮" | LLM 感谢 + 引导关注 |
| 违规弹幕 | "加微信 xxx" | 敏感词拦截，不回复 |
| 5 路同时开播 | 5 个直播间同时跑 | 无延迟累积、无 OOM |

---

## 6. 成本估算

### 6.1 月成本明细 (5路并发)

| 项目 | 产品 | 月费 (开发/测试) | 月费 (正式运营) |
|---|---|---|---|
| ECS 24C 48G | 阿里云 ECS | ¥400 按量 | ¥350 包年 |
| 带宽 50Mbps | ECS 固定带宽 | ¥1500 | ¥1500 |
| PostgreSQL | RDS 2C4G | ¥300 | ¥500 (升配) |
| Redis | 云 Redis 1GB | ¥150 | ¥200 |
| Kafka | 消息队列 Kafka | ¥500 | ¥800 |
| OSS | 对象存储 100GB | ¥20 | ¥50 |
| 向量库 | DashVector | ¥200 | ¥400 |
| 日志 | SLS | ¥100 | ¥200 |
| TTS API | 阿里云 CosyVoice | ¥180/月 | ¥300/月 (10路) |
| LLM API | DeepSeek | ¥75/月 | ¥150/月 |
| **合计** | | **¥3,425/月** | **¥4,450/月** |

> 对比原自建 GPU 方案 (¥13,800-21,300/月) — **省了 75%**

### 6.2 什么时候该上 GPU

| 触发条件 | 迁移内容 |
|---|---|
| TTS API 月费 > ¥2,000 | 买 1×L40S 自建 CosyVoice2，月摊 ¥1,500 |
| LLM API 月费 > ¥500 | 买 1×L40S 自建 Qwen-3-7B vLLM |
| render-svc 需要真人级口型 | 买 1×L40S 跑 Wav2Lip |
| 中间件月费 > ¥5,000 | 买 CPU 服务器自建 PG/Redis/Kafka |

---

## 7. Phase 3 升级路径

Phase 2 用在线 API 跑通后，Phase 3 按需将以下能力本地化：

| Phase 2 (云) | Phase 3 (本地) | 什么时候触发 |
|---|---|---|
| 阿里云 TTS API | CosyVoice2 + L40S | TTS 月费 > ¥2,000 |
| DeepSeek API | Qwen-3-7B + vLLM + L40S | LLM 月费 > ¥500 或延迟不满足 |
| 2D Viseme | Wav2Lip + L40S | 需要真人形象口型渲染 |
| 阿里云中间件 | 自建 PG/Redis/Kafka | 中间件月费 > ¥5,000 |
| DashVector | Milvus 集群 | 向量 > 100万 |
| 无微调 | LoRA 微调 Qwen (A100 按需) | 通用模型不够好 |
| 2D 虚拟形象 | 3DGS/NeRF 克隆真人形象 | Phase 3 核心交付 |

### Phase 3 架构扩展 (届时新增)

```
GPU 服务器 (按需添加):
├── GPU-1 (L40S): render-svc (Wav2Lip / 3DGS)
├── GPU-2 (L40S): tts-svc (CosyVoice2) + llm-svc (Qwen-3-7B)

新增服务:
├── clone-pipeline-svc: 全人克隆编排
└── gesture-svc: 动作/表情克隆

Proto/数据模型已在 Phase 1 预留 (2026-07 更新):
├── avatar.proto: CloneMethod, CloneConfig, 3D_REAL
├── voice.proto: FewShotConfig, SpeakerEmbedding
├── render.proto: ExpressionOverride, GestureConfig
├── avatar.py: clone_method, source_video_url, clone_quality
└── voice.py: clone_method, speaker_embedding_url, few_shot_config
```

---

## 8. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|---|---|---|---|
| 阿里云 TTS API 延迟不稳定 (>500ms) | 中 | 高 | 预生成高频回复缓存（Redis），首包 0ms；备选讯飞 TTS |
| DeepSeek API 限流/宕机 | 低 | 中 | 自动降级到关键词模板回复；备选通义千问 API |
| 2D Viseme 口型跟音频不同步，效果差 | 中 | 中 | 调整音素映射表，允许初始版本精度较低；预留 Wav2Lip 接口 |
| NLP 0.5B 电商准确率不够 | 中 | 中 | 先用通用模型上线，收集标注数据后微调；Phase 1 关键词规则兜底 |
| FFmpeg 5路 720p 推流 CPU 吃满 | 低 | 中 | 降到 540p（手机端无感知）；开硬件编码（Intel QSV） |
| 中间件用量上去了费用超预期 | 低 | 中 | 先用 docker-compose 本地跑，数据量上去了再按需切 |

---

## 9. 验收标准

### 9.1 功能验收

- [ ] 弹幕输入 → 数字人口播回复 + 嘴型同步 + RTMP 推流 → 可观看
- [ ] 5 个直播间同时开播，不相互影响
- [ ] 敏感词正确拦截（误拦 < 5%，漏拦 < 1%）
- [ ] LLM 回复合理率 > 80%（人工评估 100 条）
- [ ] 高频回复（"欢迎"、"谢谢关注"）缓存命中，延迟 < 100ms
- [ ] 情感 TTS 有明显区分度
- [ ] DeepSeek API 不可用时自动降级关键词模板
- [ ] 2D 虚拟形象口型与语音基本同步（人眼感知自然）

### 9.2 性能验收 (5路并发)

- [ ] 端到端延迟 (弹幕 → 画面) < 1.5s (P95)
- [ ] TTS 首包 < 300ms
- [ ] NLP 分析 < 50ms (P99)
- [ ] 单路推流 720p@30fps 无掉帧
- [ ] ECS CPU < 60%，内存 < 70%
- [ ] 7×24 小时无 OOM 无泄漏

### 9.3 运维验收

- [ ] `docker compose up -d` 一键启动
- [ ] 每个服务 `/api/v1/health`
- [ ] 关键错误有结构化日志
- [ ] TTS/LLM API 调用有耗时监控

---

## 附录 A：快速启动命令备忘

```bash
# 1. 启动中间件 (开发用 docker-compose)
docker compose up -d                               # PG + Redis + Kafka
docker compose --profile phase2 up -d               # + Milvus + MinIO

# 2. 配置 API Key
export TTS_ALIYUN_API_KEY="xxx"
export TTS_BACKEND="cloud"                          # mock/cloud
export DEEPSEEK_API_KEY="sk-xxx"

# 3. 启动微服务
docker compose -f docker-compose.services.yml up -d  # 15 个服务

# 4. 模拟弹幕测试
curl -X POST http://localhost:8080/api/v1/live/danmaku \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"live_room_id": "room_001", "text": "这个口红多少钱"}'

# 5. 观看推流
ffplay rtmp://localhost:1935/live/room_001
```

---

> **文档维护:** 每个步骤完成后加 `✅ 完成 (日期)` 标记。
>
> **相关文档:**
> - [架构设计](./Architecture-数字人直播平台-工业级架构设计.md)
> - [代码开发执行计划](./代码开发执行计划.md)
> - [CLAUDE.md](../CLAUDE.md)
