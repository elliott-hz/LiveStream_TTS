# Phase 2: AI 集成实施计划

> **版本:** v1.0
> **日期:** 2026-07-14
> **目标规模:** 5 路并发直播（1-5 个租户）
> **前置状态:** Phase 1 MVP 骨架已完成（16 个微服务、gRPC + Kafka、CI/CD、~500 测试）

---

## 目录

1. [Phase 2 范围与目标](#1-phase-2-范围与目标)
2. [硬件采购清单](#2-硬件采购清单)
3. [模型获取清单](#3-模型获取清单)
4. [代码实施步骤](#4-代码实施步骤)
5. [全链路联调方案](#5-全链路联调方案)
6. [简化策略：5 路可暂缓项](#6-简化策略5-路可暂缓项)
7. [工作量估算与时间线](#7-工作量估算与时间线)
8. [风险与应对](#8-风险与应对)
9. [验收标准](#9-验收标准)

---

## 1. Phase 2 范围与目标

### 1.1 一句话定义

将 Phase 1 的"空壳微服务"升级为"能真正跑通的 AI 数字人直播系统"——让 5 个直播间同时开播，数字人能听懂弹幕、生成回复、用带情感的语音说出来、并且嘴型对得上。

### 1.2 Phase 2 包含

| 能力 | 对应服务 | 核心模型 | 交付物 |
|---|---|---|---|
| 语音合成 (TTS) | `tts-svc` | CosyVoice2 + TensorRT | 流式情感语音输出，RTF < 0.3，首包 < 200ms |
| 口型渲染 | `render-svc` | Wav2Lip | 1080p@30fps 口型同步，误差 < 80ms |
| 直播互动 LLM | **`llm-svc`（新建）** | Qwen-3-7B-Instruct (INT8) + vLLM | 弹幕回复生成，延迟 < 500ms |
| NLP 语义理解 | `nlp-svc` | 0.5B 分类模型（CPU） | 意图识别、情感分析、敏感词双模检测 |
| 知识库 RAG | `knowledge-svc` | Milvus + Embedding | 商品知识检索，增强回复准确性 |
| 推流编码 | `stream-svc` | FFmpeg (CPU) | RTMP 推流到抖音/淘宝/京东 |
| 自托管 LLM | `llm-svc` | Qwen-3-7B + LoRA | 替代 Phase 1 的 DeepSeek API 占位 |

### 1.3 Phase 2 不包含（挪到 Phase 3）

- ❌ LoRA 微调训练管线（5 路直接用开源权重够用）
- ❌ 3D 数字人形象（Unity/UE5 渲染）
- ❌ 跨境 TikTok 适配
- ❌ 多语言/方言 TTS
- ❌ API 对外开放
- ❌ 分佣/结算体系

---

## 2. 硬件采购清单

### 2.1 GPU 服务器（2 台）

| 项目 | GPU-1 | GPU-2 |
|---|---|---|
| **用途** | `render-svc` 独占 | `tts-svc` + `llm-svc` 共享 |
| **GPU** | **1 × NVIDIA L40S (48GB)** | **1 × NVIDIA L40S (48GB)** |
| **为什么 L40S** | Wav2Lip 单卡跑 4-8 路，5 路占 60-100%，必须独占 | CosyVoice2 ~6GB + Qwen-3-7B INT8 ~8GB ≈ 14GB，5 路不到 20% 利用率 |
| **CPU** | 16C | 16C |
| **内存** | 64GB | 64GB |
| **系统盘** | 200GB NVMe | 200GB NVMe |
| **数据盘** | 500GB NVMe（模型+缓存） | 500GB NVMe（模型文件） |
| **网络** | 万兆网卡 | 万兆网卡 |
| **操作系统** | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| **CUDA** | 12.1 | 12.1 |
| **NVIDIA Driver** | ≥ 525 | ≥ 525 |

> **云上租用参考价:** 阿里云 ecs.gn7i-c16g1.4xlarge (1×L40S) ≈ ¥5,000-8,000/月/台
> **竞价/Spot 实例:** 可压到 ¥3,000-5,000/月
> **物理服务器买断:** 约 ¥8-15 万/台，适合长期使用

### 2.2 CPU 服务器（1 台）

**5 路并发场景下，一台高配服务器装下全部中间件和微服务：**

| 组件 | 推荐配置 | 实际分配 |
|---|---|---|
| **CPU** | **48 核** (单路 AMD EPYC 或双路 Xeon) | |
| **内存** | **96GB DDR4 ECC** | |
| **系统盘** | 500GB NVMe SSD | |
| **数据盘** | 2TB NVMe SSD | |

**资源分配明细：**

| 服务组 | CPU | 内存 | 说明 |
|---|---|---|---|
| 中间件（PG + Redis + Kafka + MinIO + Milvus + ES） | 24C | 48GB | 全单机模式，无集群 |
| 15 个微服务（gateway、user、product、script、live-mgr、avatar、voice、knowledge、nlp、interact、analytics、billing、audit、platform-sync、profile） | 16C | 32GB | 5 路并发几乎空闲 |
| stream-svc（FFmpeg 推流） | 4C | 8GB | 5 路 H.264 编码 |
| 监控（Prometheus + Grafana） | 4C | 8GB | 基础监控 |
| **合计** | **48C** | **96GB** | |

> **如果拆成 2 台:** 一台 32C 64G 跑中间件（PG/Redis/Kafka/Milvus/MinIO/ES），一台 16C 32G 跑微服务。
> **云上参考价:** 阿里云 ecs.g7.8xlarge (32C 128G) ≈ ¥4,000-6,000/月

### 2.3 A100 微调卡（Phase 2 不买）

架构设计里有 1×A100 (80GB) 用于每周 LoRA 微调 Qwen-3-7B。理由：

1. **5 路并发不需要微调**——Qwen-3-7B 开箱即用，通用能力足够
2. **微调可以云端按需**——一周跑一次，几小时就够，¥30-50/小时，月成本 ¥500-800
3. **等用户量上来再买**——当直播间有领域特殊性（如美妆术语），微调 ROI 才高

### 2.4 带宽需求

| 项目 | 计算 | 带宽 |
|---|---|---|
| 单路推流 (1080p@30fps H.264) | 5 Mbps | — |
| 5 路并发推流 | 5 × 5 | 25 Mbps |
| API/信令/TTS 音频分发 | 额外 5-10 Mbps | 5-10 Mbps |
| 50% 余量 | 30 × 1.5 | **≈ 50 Mbps 上行** |

> 家用光纤 100M 上行够用。机房 BGP 50Mbps ≈ ¥1,500-3,000/月。

### 2.5 总成本一览

| 项目 | 云服务（月费） | 自建机房（月均） |
|---|---|---|
| 2 × L40S GPU 服务器 | ¥8,000-12,000 | ¥2,000-3,000 |
| 1 × 高配 CPU 服务器 | ¥3,000-5,000 | ¥1,000-2,000 |
| 带宽 50Mbps | ¥2,000-3,000 | ¥1,000-2,000 |
| DeepSeek API 兜底 | ¥300-500 | ¥300-500 |
| LoRA 微调（云端按需） | ¥500-800 | ¥500-800 |
| **合计** | **¥13,800-21,300/月** | **¥4,800-8,300/月** |

---

## 3. 模型获取清单

### 3.1 模型下载

| 模型 | 来源 | 大小 | 用途 | 部署服务 |
|---|---|---|---|---|
| **CosyVoice2** | [ModelScope](https://modelscope.cn/models/iic/CosyVoice2-0.5B) 或 HuggingFace | ~2GB | 中文 TTS 语音合成 | `tts-svc` (GPU) |
| **Wav2Lip** | [GitHub: Rudrabha/Wav2Lip](https://github.com/Rudrabha/Wav2Lip) | ~200MB | 口型同步 | `render-svc` (GPU) |
| **Qwen-3-7B-Instruct** | [ModelScope](https://modelscope.cn/models/Qwen/Qwen3-7B-Instruct) 或 HuggingFace | ~14GB (FP16) / ~7GB (INT8) | 直播互动回复生成 | `llm-svc` (GPU) |
| **0.5B NLP 分类模型** | 需自己微调或用开源小模型(text2vec-base-chinese 等) | ~1GB | 意图/情感/敏感词 | `nlp-svc` (CPU) |
| **text2vec-base-chinese** | HuggingFace: shibing624/text2vec-base-chinese | ~400MB | 知识库 Embedding | `knowledge-svc` (CPU) |

### 3.2 模型转换（部署前必须执行）

| 步骤 | 输入 | 输出 | 工具 | 耗时 |
|---|---|---|---|---|
| CosyVoice2 → TensorRT | PyTorch checkpoint | TensorRT engine (.plan) | `trtexec` / TensorRT Python API | ~30 分钟 |
| Qwen-3-7B FP16 → INT8 | HuggingFace 权重 | INT8 量化权重 | vLLM 内置量化 或 AutoGPTQ | ~1 小时 |
| Qwen-3-7B → vLLM 格式 | HF 权重 | vLLM 可加载格式 | vLLM convert | ~10 分钟 |

> ⚠️ TensorRT 转换需要与部署环境**相同型号的 GPU**。如果你在 L40S 上转换，只能在 L40S 上跑。不能在一台 A100 上转完放到 L40S 上用。

---

## 4. 代码实施步骤

### 总览

```
步骤 1         步骤 2         步骤 3         步骤 4         步骤 5         步骤 6         步骤 7
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│新建      │  │tts-svc   │  │render-svc│  │nlp-svc   │  │knowledge │  │llm-svc   │  │全链路    │
│llm-svc   │→ │模型挂载  │→ │Wav2Lip   │→ │模型加载  │→ │Milvus    │→ │替代      │→ │联调      │
│服务框架  │  │情感引擎  │  │口型渲染  │  │分类+检测 │  │RAG对接   │  │DeepSeek  │  │端到端    │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
  3-5 天         5-7 天         5-7 天         3-4 天         3-4 天         2-3 天         3-5 天
```

### 步骤 1: 新建 llm-svc（最大改动）

**当前状态:** `services/llm-svc/` 目录不存在。`interact-svc` 直接调 DeepSeek API。

**目标:** 自托管 Qwen-3-7B，提供 gRPC 推理接口。

**新建目录结构：**

```
services/llm-svc/
├── Dockerfile                    # nvidia/cuda:12.1 + vLLM
├── requirements.txt              # vllm, transformers, peft, torch
├── pyproject.toml
├── k8s/
│   ├── configmap.yaml
│   ├── deployment.yaml           # nvidia.com/gpu: 1, nodeSelector nvidia-l40s
│   └── service.yaml              # gRPC 50069
├── src/
│   ├── __init__.py
│   ├── main.py                   # gRPC server + HTTP health 入口
│   ├── config.py                 # LLMConfig: model_path, quantization, max_batch_size
│   ├── api/
│   │   ├── __init__.py
│   │   └── grpc_impl.py         # GenerateReply, StreamReply, Health RPC 实现
│   ├── engine/
│   │   ├── __init__.py
│   │   └── vllm_engine.py       # vLLM AsyncLLMEngine 封装
│   └── services/
│       ├── __init__.py
│       ├── chat_service.py       # 多轮对话管理、prompt 模板、上下文窗口
│       └── lora_service.py       # LoRA 适配器热加载/卸载（Phase 3 启用）
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_chat_service.py
```

**新增 Proto 定义** (`libs/proto/llm/v1/llm.proto`)：

```protobuf
service LLMService {
  rpc GenerateReply(GenerateReplyRequest) returns (GenerateReplyResponse);
  rpc StreamReply(GenerateReplyRequest) returns (stream GenerateReplyResponse);
  rpc Health(HealthRequest) returns (HealthResponse);
}

message GenerateReplyRequest {
  string session_id = 1;
  repeated ChatMessage history = 2;    // 多轮对话历史
  string system_prompt = 3;            // 系统提示词（含商品/RAG 上下文）
  string user_message = 4;             // 当前弹幕内容
  int32 max_tokens = 5;
  float temperature = 6;
}

message ChatMessage {
  string role = 1;    // "user" | "assistant" | "system"
  string content = 2;
}
```

**关键实现细节：**
- `vllm_engine.py`: 启动时加载 Qwen-3-7B-Instruct (INT8)，配置 max_num_seqs=32（5 路远超够用）
- `chat_service.py`: prompt 模板 = 系统人设 + 商品信息 + 直播间氛围 + 弹幕历史
- `config.py`: `LLM_MODEL_PATH=/models/qwen3-7b-int8`, `LLM_MAX_BATCH_SIZE=8`, `LLM_GPU_MEMORY_UTILIZATION=0.6`

**改写 interact-svc:** `orchestrator.py` 中 LLM 调用从 `DeepSeek API` → `llm-svc gRPC`。

**依赖:**
```txt
vllm>=0.6.0
transformers>=4.44.0
torch>=2.3.0
peft>=0.12.0
```

### 步骤 2: tts-svc 模型挂载

**当前状态:** 骨架完整（cache、dsp、emotion、engine、linguistic、mixer、preprocessor、session、speaker 等模块目录已建），但 `engine/` 里是占位代码。

**核心改造文件：**

| 文件 | 改造内容 |
|---|---|
| `modules/engine/cosyvoice_engine.py` | CosyVoice2 模型加载 + TensorRT 推理；warmup 时预加载常用音色；RTF 监控（目标 < 0.3） |
| `modules/emotion/emotion_engine.py` | 根据 NLU 情感标签选择音色风格（开心→明亮、悲伤→低沉、愤怒→急促）；情感强度参数映射到 TTS 韵律控制 |
| `modules/cache/audio_cache.py` | Redis 缓存高频 TTS 结果（如"欢迎新朋友"）；TTL 1 小时；命中率目标 > 60% |
| `modules/speaker/speaker_manager.py` | 音色注册/切换；每个 Store 最多绑定 N 个音色（PlanQuota 控制） |
| `modules/preprocessor/text_preprocessor.py` | 数字/日期/价格标准化；SSML 标签处理（`<break>`, `<prosody>`） |
| `modules/dsp/postprocessor.py` | 音频后处理：重采样、音量归一化、拼接平滑 |
| `modules/linguistic/` | 多音字消歧、儿化音处理、轻声规则 |
| `src/api/grpc_impl.py` | 实现 `Synthesize`（请求-响应）和 `StreamingSynthesize`（流式）RPC |
| `src/http/routes.py` | WebSocket 端点：接收文本流 → 流式返回音频 chunk (PCM/MP3) |
| `config.py` | `TTS_MODEL_PATH=/models/cosyvoice2`；`TTS_USE_GPU=true`；`TTS_MAX_CONCURRENT=30` |

**验收标准:**
- 输入中文文本 → 输出 24kHz PCM 音频流
- 首包延迟 < 200ms（流式模式）
- RTF < 0.3（5 路并发时）
- 情感标签传入后，音色有明显区分度

### 步骤 3: render-svc Wav2Lip 接入

**当前状态:** `renderer/` 目录有 `compositor.py`、`lipsync.py`、`overlays.py` 骨架。

**核心改造文件：**

| 文件 | 改造内容 |
|---|---|
| `renderer/lipsync.py` | Wav2Lip 模型加载；输入：TTS 音频 + 参考人脸帧 → 输出：口型参数序列 |
| `renderer/compositor.py` | 合成管线：背景 + 数字人形象 + 口型变形 + 叠加层（商品卡、优惠券）→ 1080p@30fps 帧序列 |
| `renderer/overlays.py` | 动态叠加层：商品卡片、促销标签、弹幕飘屏；根据 `interact-svc` AI 场控指令控制显隐 |
| `src/api/grpc_impl.py` | 实现 `RenderFrame` RPC：接收 TTS 音频 chunk → 返回渲染帧 |
| `config.py` | `GPU_DEVICE=0`；`GPU_MEMORY_FRACTION=0.8`；`FPS=30`；`FRAME_WIDTH=1920` |

**管线设计（per stream）：**

```
TTS 音频 chunk → Wav2Lip 推理 → 口型参数 → 合成帧 → FFmpeg pipe → stream-svc
                   (GPU)           (GPU)      (GPU)
```

**验收标准:**
- 输入 TTS 音频 + 形象 ID → 输出 1080p@30fps 视频帧
- 口型同步误差 < 80ms
- 5 路并发时帧率不下降

### 步骤 4: nlp-svc 模型加载

**当前状态:** `classifiers/` 和 `detectors/` 目录已建，`nlp-svc` Dockerfile 是 CPU 镜像。

**核心改造文件：**

| 文件 | 改造内容 |
|---|---|
| `classifiers/intent.py` | 加载 0.5B 意图分类模型；分类类别：询价、砍价、产品咨询、闲聊、负面反馈等 12+ 意图 |
| `classifiers/sentiment.py` | 情感分类：正面/中性/负面 + 强度 1-5 |
| `detectors/sensitive.py` | **双模检测：** AC 自动机（毫秒级，覆盖已知敏感词库）→ 语义模型（0.5B，检测变体/谐音/上下文敏感） |
| `detectors/entity.py` | 实体抽取：商品名、价格、数量、颜色、尺码 |
| `src/api/grpc_impl.py` | 实现 `AnalyzeIntent`、`AnalyzeSentiment`、`DetectSensitive`、`ExtractEntities` RPC |

**AC 自动机词库：**
- 抖音/淘宝/京东平台违禁词列表（需从各平台 API 拉取 + 手动维护）
- 行业敏感词（虚假宣传、绝对化用语、医疗宣称等）

**验收标准:**
- 意图分类延迟 < 50ms (P99)
- 敏感词 AC 自动机 < 5ms；语义模型 < 100ms
- CPU 负载下 5 路并发不受影响

### 步骤 5: knowledge-svc Milvus 对接

**当前状态:** `knowledge-svc` 骨架存在，Milvus 在 docker-compose phase2 profile 中。

**核心改造文件：**

| 文件 | 改造内容 |
|---|---|
| `src/services/embedding_service.py` | text2vec-base-chinese 加载；文本 → 768 维向量 |
| `src/services/vector_store.py` | Milvus collection 管理；插入/更新/删除/检索 |
| `src/services/knowledge_service.py` | 文档上传 → 分段 → Embedding → 入库；检索 → 重排序 |
| `src/api/grpc_impl.py` | 实现 `SearchKnowledge` RPC：输入 query → 返回 TopK 相关片段 |

**Collection Schema:**
```
knowledge_base_id (VARCHAR, partition key)
chunk_id (VARCHAR, primary key)
embedding (FLOAT_VECTOR, 768 dim)
text (VARCHAR)
metadata (JSON)
```

**验收标准:**
- 单次检索延迟 < 100ms（Top 5）
- 召回率 > 80%（与商品相关的查询能正确返回知识片段）

### 步骤 6: llm-svc 替代 DeepSeek API

**当前状态:** 步骤 1 已建好 llm-svc。这一步做集成。

**改造文件：**

| 文件 | 改造内容 |
|---|---|
| `interact-svc/src/pipeline/orchestrator.py` | 把 `call_deepseek_api()` 替换为 `call_llm_svc_grpc()`；加入 RAG 上下文拼 prompt |
| `interact-svc/src/config.py` | 添加 `LLM_SVC_GRPC_HOST`、`LLM_SVC_GRPC_PORT` 配置项 |
| `interact-svc/src/services/reply_service.py` | 添加 DeepSeek API 兜底：llm-svc 不可用时自动降级到 DeepSeek API |

**Prompt 组装逻辑：**

```
[System] 你是{store_name}的AI主播{avatar_name}，性格{persona}。
         当前在播商品：{product_name}，价格{price}，卖点{highlights}。
         相关知识：{rag_context}
         回复要求：自然口语化，20-50字，可以带emoji。

[Context] 最近 5 条弹幕：{recent_danmaku}

[User] 当前弹幕：{danmaku_text}
[Intent] {intent_label}  [Sentiment] {sentiment_label}

→ LLM → 回复文本 → TTS 合成 → Wav2Lip 渲染 → RTMP 推流
```

### 步骤 7: 全链路联调

**目标:** 验证端到端流程可跑通。

**联调环境:**
- Docker Compose 拉起全部基础设施（PG、Redis、Kafka、MinIO、Milvus）
- 各服务独立启动（不用 K8s——5 路没必要）
- `static/index.html` 作为调试前端：发弹幕 → 看到回复 + 听到语音 + 看到口型

**测试场景清单：**

| 场景 | 输入 | 期望输出 |
|---|---|---|
| 产品咨询 | "这个口红多少钱" | LLM 回复价格 + TTS 语音播报 |
| 砍价 | "便宜点行不行" | LLM 回复优惠信息 + 弹优惠券叠加层 |
| 负面评论 | "质量太差了" | 敏感词检测通过（不违规），LLM 安抚回复 |
| 闲聊 | "主播好漂亮" | LLM 感谢 + 引导关注 |
| 违规弹幕 | "加微信 xxx" | 敏感词检测拦截，不生成回复 |
| 5 路同时开播 | 5 个直播间同时跑上述场景 | 全部正常，无延迟积累、无 OOM |

**联调顺序：**

```
1. 基础设施验证: docker compose --profile phase2 up -d
2. tts-svc 独立验证: HTTP POST → 返回音频文件
3. nlp-svc 独立验证: gRPC 调用 → 返回意图/情感/敏感词
4. llm-svc 独立验证: gRPC Prompt → 返回回复文本
5. render-svc 独立验证: 音频 + 形象 → 返回视频帧
6. stream-svc 独立验证: 视频帧 → RTMP 推流 → VLC 播放
7. interact-svc 管线验证: 弹幕 → 全链路 → 视频流输出
8. 5 路并发压测: 5 个直播间同时跑，观察 GPU 利用率/延迟/OOM
```

---

## 5. 全链路联调方案

### 5.1 端到端数据流

```
抖音/淘宝 直播间
      │
      │ 弹幕 WebSocket
      ▼
┌─────────────┐
│ gateway-svc  │  JWT 鉴权 + 限流 + 路由
└──────┬──────┘
       │ gRPC
       ▼
┌──────────────┐    ┌─────────────┐
│ interact-svc  │───→│  nlp-svc    │  意图/情感/敏感词
│  (pipeline)  │    │  (CPU)      │
│              │───→│ knowledge   │  RAG 检索
│              │    │  -svc       │
│              │───→│  llm-svc    │  生成回复
│              │    │  (GPU)      │
└──────┬───────┘    └─────────────┘
       │
       │ 回复文本 + 场控指令
       ▼
┌─────────────┐
│  tts-svc    │  CosyVoice2 流式合成 (GPU)
└──────┬──────┘
       │ PCM 音频流
       ▼
┌─────────────┐
│ render-svc  │  Wav2Lip 口型渲染 (GPU)
└──────┬──────┘
       │ 1080p@30fps 视频帧
       ▼
┌─────────────┐
│ stream-svc  │  FFmpeg 编码 → RTMP 推流 (CPU)
└──────┬──────┘
       │ RTMP
       ▼
   直播平台 (抖音/淘宝/京东)
```

### 5.2 关键延迟预算

| 环节 | 目标延迟 | 累计 |
|---|---|---|
| gateway → interact | < 10ms | 10ms |
| nlp-svc 分析 | < 50ms | 60ms |
| knowledge-svc RAG | < 100ms | 160ms |
| llm-svc 生成 | < 500ms | 660ms |
| tts-svc 首包 | < 200ms | 860ms |
| render-svc 首帧 | < 100ms | 960ms |
| stream-svc 编码 | < 50ms | 1010ms |
| **端到端（弹幕 → 画面输出）** | **< 1.2 秒** | |

---

## 6. 简化策略：5 路可暂缓项

以下是架构文档里设计好了但 **5 路并发不需要** 的东西——等用户量上去了再加：

| 暂缓项 | 原因 | 何时加回来 |
|---|---|---|
| **K8s 多节点集群** | 一台 Docker Compose 跑全部服务足够 | 日活商家 > 20 个 |
| **A100 LoRA 微调** | Qwen-3-7B 开箱够用，云端按需微调更便宜 | 回复质量明显不够好时 |
| **Elasticsearch 日志聚合** | 5 路日志量小，stdout + `docker logs` 就行 | 微服务实例 > 20 个 |
| **Istio 服务网格** | 流量小，不需要灰度/熔断/限流那么复杂 | 服务间调用链 > 3 层且频繁 |
| **ArgoCD GitOps** | 手动 `docker compose up -d` 比配 GitOps 快 | 需要多环境（dev/staging/prod）时 |
| **Milvus 集群模式** | Standalone 模式支持百万级向量，5 个知识库远不到 | 知识库总量 > 100 万条 |
| **PostgreSQL 主从** | 单机 PG 每天自动备份足够 | 数据不能丢、需要 HA 时 |
| **GPU 池化管理（MIG/MPS）** | 5 路不需要 GPU 切分，整卡分配就行 | GPU 利用率 < 40% 需要共享时 |
| **HPA 自动扩缩容** | 5 路流量稳定，手动设定 replica=1 即可 | 流量波动 > 3× 日峰值 |

---

## 7. 工作量估算与时间线

### 7.1 人力资源假设

- **1 名 AI 后端工程师**（熟悉 Python、PyTorch、gRPC）
- 全职投入

### 7.2 各步骤工作量

| 步骤 | 工作内容 | 人天 | 依赖 |
|---|---|---|---|
| 0. 环境准备 | 模型下载 + TensorRT/INT8 转换 + 硬件上架 + CUDA 驱动 | 3 | 硬件到位 |
| 1. 新建 llm-svc | 目录结构 + Proto + vLLM 引擎 + chat service + gRPC API | 5 | 步骤 0 |
| 2. tts-svc 模型挂载 | CosyVoice2 引擎 + 情感引擎 + 缓存 + 流式 API | 7 | 步骤 0 |
| 3. render-svc Wav2Lip | lipsync 模型 + compositor 合成 + frame pipeline | 7 | 步骤 0 |
| 4. nlp-svc 模型加载 | 意图/情感分类 + 双模敏感词检测 + AC 词库 | 4 | 无（CPU 模型，可与 GPU 步骤并行） |
| 5. knowledge-svc Milvus | embedding + vector store + 检索 API | 4 | 步骤 0 |
| 6. llm-svc 集成 | 改写 interact-svc pipeline + DeepSeek 降级 | 3 | 步骤 1、4、5 |
| 7. 全链路联调 | 端到端测试 + 5 路压测 + Bug 修复 | 5 | 步骤 1-6 |
| **合计** | | **38 人天 ≈ 7-8 周** | |

### 7.3 周级里程碑

```
Week 1: 硬件到位 + 模型下载转换 (步骤 0)
Week 2-3: llm-svc 新建 + tts-svc 模型挂载 (步骤 1-2，可并行)
Week 3-4: render-svc Wav2Lip (步骤 3)
Week 4-5: nlp-svc + knowledge-svc (步骤 4-5，可并行)
Week 5-6: llm-svc 集成 + 各服务独立验证 (步骤 6)
Week 6-8: 全链路联调 + 5 路压测 + Bug 修复 (步骤 7)
```

### 7.4 并行化机会

如果有 **2 名工程师**：

- **工程师 A（GPU 方向）:** 步骤 1 (llm-svc) → 步骤 2 (tts-svc) → 步骤 3 (render-svc)
- **工程师 B（CPU 方向）:** 步骤 4 (nlp-svc) → 步骤 5 (knowledge-svc) → 步骤 6 (集成)
- **合流:** 步骤 7 (联调，两人一起)

→ **4-5 周完成**。

---

## 8. 风险与应对

| 风险 | 概率 | 影响 | 等级 | 应对策略 |
|---|---|---|---|---|
| CosyVoice2 TensorRT 转换失败或 RTF 不达标 | 中 | 高 | **P1** | 提前验证；备选方案：ONNX Runtime GPU；降级到 CosyVoice2 PyTorch（RTF ~0.5，5 路可接受） |
| Wav2Lip 单卡撑不住 5 路 1080p | 中 | 高 | **P1** | 降分辨率到 720p（抖音直播 720p 完全够用）；或者 2 张 L40S 各跑 2-3 路 |
| Qwen-3-7B INT8 回复质量不达预期 | 低 | 中 | **P2** | 保留 DeepSeek API 作为主方案，Qwen 做降级；或换 Qwen-3-14B 用 2×L40S |
| 硬件采购周期长，GPU 缺货 | 中 | 中 | **P2** | 先用云端 GPU 实例开发，硬件到了再迁移；L40S 供货比 A100/H100 好很多 |
| NLP 0.5B 模型对电商领域准确率不够 | 中 | 中 | **P2** | 先用通用模型上线，收集 500-1000 条标注数据后微调 |
| 端到端延迟超 2 秒，用户感知"卡顿" | 中 | 高 | **P1** | 各环节加 timeout；llm-svc 用 streaming decode 降低首 token 延迟；TTS 预生成高频回复缓存 |

---

## 9. 验收标准

### 9.1 功能验收

- [ ] 弹幕输入 → 数字人口播回复 + 嘴型同步 + RTMP 推流 → 可观看
- [ ] 支持 5 个直播间同时开播，不相互影响
- [ ] 敏感词正确拦截（误拦率 < 5%，漏拦率 < 1%）
- [ ] 意图识别准确率 > 80%（电商场景 12 类意图）
- [ ] LLM 回复合理率 > 90%（人工评估 100 条抽样）
- [ ] 高频回复（"欢迎"、"谢谢关注"等）缓存命中，延迟 < 100ms
- [ ] 情感 TTS 有明显区分度（开心/中性/悲伤 三种风格）
- [ ] DeepSeek API 降级可用（llm-svc 挂了自动切）

### 9.2 性能验收（5 路并发）

- [ ] 端到端延迟（弹幕 → 画面输出）< 1.5 秒 (P95)
- [ ] TTS 首包延迟 < 200ms
- [ ] 口型同步误差 < 80ms
- [ ] 单路推流 1080p@30fps 无掉帧
- [ ] GPU-1 (render) 利用率 < 90%，无 OOM
- [ ] GPU-2 (tts+llm) 利用率 < 50%，无 OOM
- [ ] CPU 服务器利用率 < 60%
- [ ] 7×24 小时长时间运行无内存泄漏（内存增长 < 5%/24h）

### 9.3 运维验收

- [ ] `docker compose up -d` 一键启动全栈
- [ ] 每个服务有 `/api/v1/health` 健康检查
- [ ] GPU 服务有 `nvidia-smi` 指标暴露
- [ ] 关键错误有结构化日志 + 告警规则（Prometheus AlertManager 或钉钉通知）

---

## 附录 A：快速启动命令备忘（目标）

```bash
# 1. 启动基础设施
docker compose --profile phase2 up -d

# 2. 启动全部微服务
docker compose up -d

# 3. 检查全部健康
curl http://localhost:8080/api/v1/health           # gateway
for port in 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091 8092 8093 8094 8095 8096; do
  curl -s http://localhost:$port/api/v1/health
done

# 4. 检查 GPU 服务
curl http://localhost:8008/api/v1/health           # tts-svc
curl http://localhost:8089/api/v1/health           # render-svc  
curl http://localhost:8069/api/v1/health           # llm-svc (新建)

# 5. 查看 GPU 利用率
ssh gpu-1 "nvidia-smi"
ssh gpu-2 "nvidia-smi"

# 6. 模拟弹幕测试
curl -X POST http://localhost:8080/api/v1/danmaku \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"live_room_id": "xxx", "text": "这个口红多少钱"}'

# 7. 观看推流
ffplay rtmp://localhost:1935/live/room_001
```

---

## 附录 B：GPU 选型对比

| GPU | 显存 | FP16 算力 | 适用服务 | 参考价（云/月） | 判断 |
|---|---|---|---|---|---|
| **L40S** | 48GB | 362 TFLOPS | render + tts + llm | ¥5,000-8,000 | ✅ **推荐**，性价比最优 |
| A10 | 24GB | 125 TFLOPS | tts only | ¥3,000-5,000 | ⚠️ Wav2Lip 5 路跑不动（只能 2-3 路） |
| A100 | 80GB | 312 TFLOPS | 微调训练 | ¥12,000-18,000 | ❌ 太贵，5 路严重过剩 |
| H100 | 80GB | 989 TFLOPS | 大规模训练 | ¥25,000+ | ❌ 完全没必要 |
| T4 | 16GB | 65 TFLOPS | 轻度 NLP | ¥1,500-2,500 | ❌ 显存不够跑 CosyVoice2 + Qwen |
| RTX 4090 | 24GB | 330 TFLOPS | 开发调试 | ¥2,000-4,000 | ⚠️ 数据中心不可用，仅开发机 |

---

> **文档维护:** 本文件随 Phase 2 实施进度更新。每个步骤完成后，在该步骤标题下添加 `✅ 完成 (日期)` 标记和实际耗时。
>
> **相关文档:**
> - [PRD v2.0](./PRD-数字人直播带货平台-需求文档.md)
> - [架构设计 v3.1](./Architecture-数字人直播平台-工业级架构设计.md)
> - [代码开发执行计划 v1.0](./代码开发执行计划.md)
> - [竞品对比与差异化分析](./竞品对比与差异化分析.md)
