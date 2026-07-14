# TTS Platform — 顶层技术架构设计

> **前提条件**
> - **系统总输入**：上游 LLM / Agent 输出的文本
> - **系统总输出**：Streaming PCM（16kHz, mono, signed 16-bit, little-endian）
> - **POC 验证形式**：流式合成通路（WebSocket / gRPC），**不支持 REST 同步/异步合成**
> - **设计原则**：模块化、分层、接口分离
> - **架构范围**：覆盖完整处理流程的所有逻辑模块。POC 实现时可简化或 Mock，但流程不断

---

## 一、架构总览

### 1.1 系统边界

```
  ┌───────────────────────────────────────────────────────────────┐
  │                       TTS System                              │
  │                                                               │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
  │  │Gateway  │  │Session  │  │ Text    │  │Linguistic│          │
  │  │(M1)     │  │Manager  │  │Preproc  │  │Engine   │          │
  │  │         │  │(M2)     │  │(M3)     │  │(M4)     │          │
  │  └────┬────┘  └─────────┘  └─────────┘  └────┬────┘          │
  │       │                                       │               │
  │       ▼                                       ▼               │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
  │  │Emotion  │  │ Speaker │  │  TTS    │  │  DSP   │           │
  │  │& Style  │  │ Manager │  │ Engine  │  │(M8)    │           │
  │  │(M5)     │  │(M6)     │  │(M7)     │  │        │           │
  │  └─────────┘  └─────────┘  └────┬────┘  └─────────┘          │
  │                                  │                            │
  │  ┌─────────┐  ┌─────────┐       │                            │
  │  │ Cache   │  │ Mixer   │◄──────┘                            │
  │  │(M9)     │  │(M10)    │                                    │
  │  └─────────┘  └─────────┘                                    │
  └───────────────────────────────────────────────────────────────┘
       ▲                                                   │
       │ WS / gRPC                                         │ Streaming PCM
       │                                                   ▼
  LLM / Agent                                       Digital Human / APP
  (上游系统)                                          (下游系统)
```

### 1.2 模块划分

| 模块 | 名称 | 职责 | 依赖 |
|:----:|------|------|:----:|
| **M1** | **TTS Streaming Gateway** | 流式接入层。WS/gRPC 协议适配、文本接收、音频推送、控制帧处理 | M2, M7 |
| **M2** | **Session Manager** | 流式会话生命周期。状态管理、超时清理 | — |
| **M3** | **Text Preprocessor** | 文本预处理。Text Normalization（数字/日期/货币/URL/Emoji 转写）、特殊符号清洗 | — |
| **M4** | **Linguistic Processing Engine** | 语言学处理。G2P（字音转换）、Prosody 预测（停顿/重音/语调）、拼音标注 | M5 |
| **M5** | **Emotion & Style Engine** | 情感与风格分析。文本语义 → 情感标签 + 强度，注入 M4 影响 Prosody 参数 | — |
| **M6** | **Speaker Manager** | 音色管理。音色 CRUD、Embedding 向量/Prompt 音频存储与加载 | — |
| **M7** | **Streaming TTS Engine** | 核心语音合成。接收音素序列+情感+音色 → 流式 PCM Chunk | M4, M5, M6, M9 |
| **M8** | **Audio Post Processing (DSP)** | 音频后处理。降噪、响度归一、EQ、静音裁剪 | — |
| **M9** | **Audio Cache** | 音频缓存。缓存已合成片段，降低 GPU 推理 | — |
| **M10** | **Audio Mixer** | 音频混音。多音轨混音（人声+BGM+音效），输出最终 PCM | — |

### 1.3 模块依赖图

```
客户端 (LLM/Agent)  ──WS/gRPC──→  M1 Gateway
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                          ▼            ▼            ▼
                       M2 Session   M3 Text      M5 Emotion
                       Manager      Preproc      & Style
                                       │            │
                                       ▼            │
                                    M4 Linguistic ──┘
                                    Engine
                                       │
                                       ▼
                          ┌────────────┼────────────┐
                          │            │            │
                          │         M6 Speaker      │
                          │         Manager         │
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                       ▼
                          ┌─────────────────────┐
                          │       M7 TTS        │
                          │       Engine        │
                          └──────────┬──────────┘
                                     │
                          ┌──────────┼──────────┐
                          │          │          │
                          ▼          ▼          ▼
                       M8 DSP    M9 Cache   M10 Mixer
                          │                   │
                          └───────────┬───────┘
                                      │
                                      ▼
                               Streaming PCM
                               → 客户端
```

### 1.4 模块接口总表

| 模块 | 对外暴露接口 | 对内调用接口 | 数据持有 |
|:----:|:------------:|:------------:|:--------:|
| **M1** | WS `/ws/v1/tts` | M2.Session CRUD | — |
| | gRPC `BidirectionalSynthesize` | M7.SynthesizeStream | — |
| **M2** | — | — | 会话状态（POC: 内存 / 生产: Redis） |
| **M3** | — | — | TN 规则表（内存） |
| **M4** | — | M5.GetEmotionTag | G2P 字典（内存） |
| **M5** | — | — | 情感分类模型 / LLM 接口 |
| **M6** | REST `/api/v1/voices/*` | — | 音色元数据（POC: JSON 文件 / 生产: PG + MinIO） |
| **M7** | — | M4.GetLinguisticFeatures | — |
| | | M5.GetEmotionTag | |
| | | M6.GetVoice | |
| | | M9.Get / M9.Set | |
| **M8** | — | — | DSP 参数配置（内存） |
| **M9** | — | — | 音频缓存（POC: 内存 dict / 生产: Redis） |
| **M10** | — | — | 混音配置（内存） |

---

## 二、逐模块设计 —— 接口 + 数据

### 2.1 M1 — TTS Streaming Gateway

#### 2.1.1 职责

- 接受客户端（LLM / Agent）的 WebSocket / gRPC 连接
- 接收文本帧 → 按会话派发到下游管线
- 从 M7 接收 PCM Chunk → 流式推回客户端
- 处理 cancel、ping/pong 等控制帧
- **不负责任何 REST 合成接口**
- **额外提供：** REST 音色管理（代理 M6）、健康检查、静态页面服务

#### 2.1.2 接口设计

**对外接口 — WebSocket**

连接：`ws://<host>:<port>/ws/v1/tts`

客户端 → 服务端（JSON 文本帧）：
```
synthesis_request {
  type: "synthesis_request",
  request_id: string,
  text: string,              // 单句 ≤ 2000 字符
  voice_id: string?,         // 默认 "default"
  emotion: string?,          // 默认 "neutral"
  speed: float?              // 默认 1.0
}

cancel { type: "cancel", request_id: string }
ping   { type: "ping" }
```

服务端 → 客户端：
```
audio_chunk {
  type: "audio_chunk",
  request_id: string,
  sequence: int,             // 0 递增
  data: string,               // Base64 PCM, 20ms/chunk
  sample_rate: 16000
}

synthesis_complete { type, request_id, total_chunks, duration_ms }
error              { type, request_id, error_code, message }
pong               { type: "pong" }
```

**对外接口 — gRPC**

```protobuf
syntax = "proto3";
package tts.v1;

service TTS {
  rpc BidirectionalSynthesize(stream ClientMessage) returns (stream ServerMessage);
  rpc Health(HealthRequest) returns (HealthResponse);
}

message SynthesizeRequest {
  string text         = 1;
  string voice_id     = 2;
  string emotion      = 3;
  float  speed        = 4;
  string request_id   = 5;
}

message CancelRequest { string request_id = 1; }
message Ping {}
message Pong {}

message ClientMessage {
  oneof payload {
    SynthesizeRequest synthesis_request = 1;
    CancelRequest     cancel            = 2;
    Ping              ping              = 3;
  }
}

message AudioChunk {
  string request_id   = 1;
  int32  sequence     = 2;
  bytes  pcm_data     = 3;
  int32  sample_rate  = 4;
}
message SynthesisComplete { string request_id = 1; int32 total_chunks = 2; int32 duration_ms = 3; }
message ErrorMessage      { string request_id = 1; int32 error_code = 2; string message = 3; }

message ServerMessage {
  oneof payload {
    AudioChunk        audio_chunk        = 1;
    SynthesisComplete synthesis_complete = 2;
    ErrorMessage      error              = 3;
    Pong              pong               = 4;
  }
}

message HealthRequest {}
message HealthResponse { string status = 1; }
```

**对内接口（M1 → M2）：**
```
M2.CreateSession(session_id, voice_id, emotion, speed) → error
M2.DestroySession(session_id) → error
M2.GetSession(session_id) → SessionState
```

**对内接口（M1 → M7）：**
```
M7.SynthesizeStream(ctx, SessionState, text)
  → on_chunk(AudioChunk)
  → on_complete(SynthesisComplete)
  → on_error(Error)
```

**额外提供的 REST 路由（POC 实现，非合成用途）：**

```
# 健康检查
GET  /api/v1/health              → {"status": "healthy", "version": "1.0.0-poc", "uptime_seconds": N}

# 音色管理（代理至 M6 SpeakerManager）
GET    /api/v1/voices             → 音色列表
GET    /api/v1/voices/{voice_id}  → 音色详情
POST   /api/v1/voices             → 创建音色
DELETE /api/v1/voices/{voice_id}  → 删除音色

# 静态页面
GET /                            → 浏览器测试客户端（static/index.html）
GET /static/{filename}           → 静态资源
```

#### 2.1.3 数据架构

**数据持有：** 无。仅维护连接 → session_id 映射（内存）。

---

### 2.2 M2 — Session Manager

#### 2.2.1 职责

- 为每个连接创建/销毁会话
- 追踪会话状态：voice_id、emotion、speed、text_buffer、last_active_at
- 超时检测：30s 无活动 → 自动销毁

#### 2.2.2 接口设计

**对内接口：**
```
CreateSession(id, voice_id, emotion, speed) → error
GetSession(id) → SessionState
UpdateSession(id, fields) → error
DestroySession(id) → error
```

**`SessionState`：**
```json
{
  "session_id": "sess-a1b2c3",
  "voice_id": "anchor_a",
  "emotion": "excited",
  "speed": 1.0,
  "text_buffer": "",
  "total_chunks": 0,
  "created_at": "2026-07-13T10:00:00Z",
  "last_active_at": "2026-07-13T10:00:05Z"
}
```

#### 2.2.3 数据架构

**POC（内存 dict）：**
```python
_sessions: dict[str, SessionState]  # key = session_id
# 空闲超时: 30s — 后台线程定期清理
# 生产规划：迁移至 Redis，TTL 30min
```

---

### 2.3 M3 — Text Preprocessor

#### 2.3.1 职责

- 将 LLM 输出的原始文本转为适合朗读的规范文本
- 纯 text→text，不涉及语音学

#### 2.3.2 接口设计

**对内接口：**
```
M3.Process(text string) → (normalized_text string, error)
```

**内部子模块：**

| 子模块 | 职责 | 示例 |
|--------|------|------|
| HTML/Markdown 清洗 | 去除标签、控制字符 | `<b>你好</b>` → `你好` |
| 数字转写 | 阿拉伯数字 → 中文数字（≤ 9999） | `123` → `一百二十三` |
| 日期转写 | 数字日期 → 自然语言 | `2026-07-13` → `二零二六年七月十三日` |
| 货币转写 | 货币符号+数字 → 金额 | `￥1999` → `一千九百九十九元` |
| URL/Email 转写 | 链接 → 可读形式 | `www.abc.com` → `三达不溜点 abc 点 com` |
| Emoji 转写 | 表情 → 文字 | `😊` → `微笑` |

**处理顺序：** HTML 清洗 → Emoji → 数字/日期/货币 → URL/Email → 量词。此顺序敏感。

#### 2.3.3 数据架构

**数据持有（内存）：**
- TN 规则表：可热加载的 JSON 配置 `{patterns: [{regex, replacement}]}`
- POC 实现：基于正则的规则引擎，无 ML 模型

**数据依赖：** 无。

---

### 2.4 M4 — Linguistic Processing Engine

#### 2.4.1 职责

- 在规范化文本上做语音学处理
- 输出音素序列 + 声学特征供 M7

#### 2.4.2 接口设计

**对内接口：**
```
M4.Process(normalized_text string, emotion_tag EmotionTag) → LinguisticFeatures
```

**`LinguisticFeatures` 输出：**
```json
{
  "phonemes": ["b", "ei", "j", "ing", ...],           // 音素序列
  "durations_ms": [120, 80, 90, ...],                  // 音素时长
  "f0_contour": [220.0, 215.5, 230.0, ...],            // 基频曲线
  "pause_positions": [                                  // 停顿位置
    {"after_phoneme_index": 7, "duration_ms": 300},
    {"after_phoneme_index": 15, "duration_ms": 200}
  ],
  "energy_contour": [0.8, 0.85, 0.9, ...],             // 能量包络
  "stress_tags": [0, 0, 1, 0, ...]                     // 重音标记
}
```

**内部子模块：**

| 子模块 | 职责 |
|--------|------|
| G2P（字音转换） | 汉字 → 拼音/音素序列 |
| 分词 | 中文分词，辅助 Prosody |
| Prosody 预测 | 停顿位置、Pitch 曲线、语速变化 |
| 重音标注 | 语义重音位置 |
| 英文/缩写处理 | 中英混合场景的发音决策 |

**`EmotionTag` 对 Prosody 的影响：**

| 情感 | 语速 | Pitch 基线 | 能量 |
|------|:----:|:----------:|:----:|
| neutral | 1.0x | 220Hz | 0.8 |
| happy | 1.1x | 260Hz | 0.9 |
| sad | 0.8x | 180Hz | 0.5 |
| excited | 1.2x | 280Hz | 1.0 |
| calm | 0.9x | 200Hz | 0.6 |

#### 2.4.3 数据架构

**数据持有（内存）：**
- G2P 词典（pypinyin / 自研）
- Prosody 模型参数（轻量 ONNX 模型 或 规则配置）

**数据依赖：**
- 读取 M5：EmotionTag（影响 Prosody 参数）

---

### 2.5 M5 — Emotion & Style Engine

#### 2.5.1 职责

- 分析文本语义 → 输出情感标签（emotion）+ 强度（intensity）
- 将情感标签注入 M4（影响 Prosody）和 M6（影响音色选择）

#### 2.5.2 接口设计

**对内接口：**
```
M5.Classify(text string) → EmotionTag
```

**`EmotionTag`：**
```json
{
  "emotion": "happy",           // neutral / happy / sad / excited / calm
  "intensity": 0.85,            // [0.0, 1.0]
  "style": "conversational"     // conversational / broadcast / storytelling
}
```

**内部处理（POC）：**
```
M5.Classify(text) {
  if client 明确指定 emotion → 直接使用
  else → 返回 neutral (1.0)
}
```

POC 暂不做语义级情感分类，保留接口供后续接入 LLM 分类。

#### 2.5.3 数据架构

**数据持有：** 无。POC 为固定规则。

**数据依赖：** 无。

---

### 2.6 M6 — Speaker Manager

#### 2.6.1 职责

- 音色元数据管理（CRUD）
- 存储音色 Embedding 向量（.npy）和 Prompt 音频（.wav）
- 提供音色数据加载接口给 M7

#### 2.6.2 接口设计

**对外接口 — REST（管理用途）：**

```
GET    /api/v1/voices              → 音色列表
GET    /api/v1/voices/{voice_id}   → 音色详情
POST   /api/v1/voices              → 创建音色
DELETE /api/v1/voices/{voice_id}   → 删除音色
```

请求/响应结构同前版。

**对内接口（供 M7 调用）：**
```
M6.GetVoice(voice_id) → VoiceProfile
M6.LoadEmbedding(voice_id) → []float32
M6.LoadPromptAudio(voice_id) → []byte
```

**`VoiceProfile`：**
```json
{
  "voice_id": "anchor_a",
  "name": "主播小A",
  "gender": "female",
  "language": "zh-CN",
  "status": "active",
  "embedding_path": "voice/embedding/anchor_a/embedding.npy",
  "prompt_audio_path": "voice/prompt/anchor_a/prompt.wav"
}
```

#### 2.6.3 数据架构

**POC（JSON 文件）：**
```
voices/{voice_id}/voice.json   ← VoiceProfile 元数据（JSON 序列化）
embedding / prompt_audio 文件     ← POC 阶段暂未存储（返回空占位符）
```

**生产规划（PostgreSQL + MinIO）：**
```sql
CREATE TABLE voice_profiles (
    id                BIGSERIAL       PRIMARY KEY,
    voice_id          VARCHAR(64)     NOT NULL UNIQUE,
    name              VARCHAR(128)    NOT NULL,
    gender            VARCHAR(8)      NOT NULL DEFAULT 'unknown',
    language          VARCHAR(16)     NOT NULL DEFAULT 'zh-CN',
    status            VARCHAR(16)     NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'disabled', 'deleted')),
    embedding_path    VARCHAR(512),
    prompt_audio_path VARCHAR(512),
    metadata          JSONB           NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_voice_status ON voice_profiles(status);
```

```
MinIO:
  voice/prompt/{voice_id}/prompt.wav
  voice/embedding/{voice_id}/embedding.npy
```

---

### 2.7 M7 — Streaming TTS Engine

#### 2.7.1 职责

- **核心语音合成**。接收 M4 的音素序列 + M5 的情感标签 + M6 的音色 → 流式 PCM
- 合成前查 M9 缓存，未命中再推理，推理后写 M9
- 每 20ms 输出一个 PCM Chunk（320 字节 @16kHz）

#### 2.7.2 接口设计

**对内接口（被 M1 调用）：**
```
M7.SynthesizeStream(
  session_id: string,
  text: string,
  voice_id: string,
  emotion: string,
  speed: float,
  on_chunk: func(AudioChunk),
  on_complete: func(SynthesisComplete),
  on_error: func(Error)
) → error
```

**内部管线：**
```
SynthesizeStream(session_id, features, emotion, speed, on_chunk, ...)
  │
  ├─ 输入: 由上游 Pipeline Runner 提前组装好的
  │   • LinguisticFeatures（M4 产出）
  │   • EmotionTag（M5 产出）
  │   • Speaker Embedding（M6 产出）
  │
  ├─ 0. 查缓存: M9.Get(cache_key)
  │     ├─ 命中 → 逐 chunk 回调 on_chunk, on_complete, 返回
  │     └─ 未命中 → 继续
  │
  ├─ 1. 模型推理（POC: 正弦波生成）
  │     ├─ 输入: linguistic_features + embedding + emotion_tag
  │     ├─ 处理: 按 Emotion 选择频率/音量生成正弦波
  │     │   （目标: CosyVoice2 / FishSpeech 推理）
  │     └─ 输出: 每 20ms PCM
  │         └─ on_chunk(AudioChunk)
  │
  ├─ 2. 写缓存: M9.Set(cache_key, full_pcm)
  └─ 3. on_complete(SynthesisComplete)
```

> **⚠️ 重要 — 管线所有权说明**：上述 `M3→M5→M4→M6→M9` 的编排**不属于 M7**。
> 在代码中，这些模块的调用由 `main.py:build_pipeline_runner()` 统一编排，
> M7 只接收准备好的 `(LinguisticFeatures, EmotionTag, embedding)` 执行推理。
> 这是架构设计的有意分离：M7 只关注"合成"，不关心"文本怎么来的"。

#### 2.7.3 数据架构

**数据持有：** 无持久化数据。

**数据依赖：**
- M3: normalized_text
- M4: linguistic_features
- M5: emotion_tag
- M6: embedding / voice_profile
- M9: cache read/write

---

### 2.8 M8 — Audio Post Processing (DSP)

#### 2.8.1 职责

- 对 TTS Engine 输出的原始 PCM 做后处理
- 确保所有音色输出音量一致、音质稳定

#### 2.8.2 接口设计

**对内接口：**
```
M8.Process(pcm_stream: chan<[]byte>) → (processed_stream: chan<[]byte>, error)
```

**DSP 流水线（按顺序）：**

| 步骤 | 处理 | 说明 |
|:----:|------|------|
| 1 | Noise Reduction | 降噪，去底噪/电流声 |
| 2 | Normalize | 响度归一化（目标 RMS -16dB） |
| 3 | Limiter | 限幅，防 clipping（threshold -1dB） |
| 4 | Silence Trim | 裁剪首尾静音段 |

**配置示例：**
```json
{
  "target_rms_db": -16.0,
  "limiter_threshold_db": -1.0,
  "silence_threshold_db": -50.0,
  "silence_min_duration_ms": 100
}
```

#### 2.8.3 数据架构

**数据持有（内存）：** DSP 参数配置。

**数据依赖：** 无。

---

### 2.9 M9 — Audio Cache

#### 2.9.1 职责

- 缓存已合成文本的完整 PCM，避免重复 GPU 推理
- 缓存键 = `md5(text):voice_id:emotion`

#### 2.9.2 接口设计

**对内接口：**
```
M9.Get(cache_key string) → (pcm_data []byte, hit bool)
M9.Set(cache_key string, pcm_data []byte, ttl Duration) → error
M9.Exists(cache_key string) → bool
```

**缓存键计算：**
```
cache_key = fmt.Sprintf("%x:%s:%s", md5(text), voice_id, emotion)
// text 取 M3 输出（normalized_text），保证一致性
```

#### 2.9.3 数据架构

**POC（内存 dict）：**
```python
_store: dict[str, tuple[bytes, float]]  # key → (pcm_data, expire_at)
# TTL: 24h
# 生产规划: 迁移至 Redis
```

---

### 2.10 M10 — Audio Mixer

#### 2.10.1 职责

- 多音轨混音。将人声 PCM + BGM PCM + 音效 PCM 混合为单路 PCM
- 每路音轨独立控制音量

#### 2.10.2 接口设计

**对内接口：**
```
M10.Mix(tracks []AudioTrack) → (mixed_pcm []byte, error)
```

**`AudioTrack`：**
```json
{
  "track_id": "human_vocal",
  "pcm_data": "<bytes>",
  "volume_db": -12.0,
  "pan": 0.0               // -1.0 (左) ~ 1.0 (右)
}
```

**混音算法：** 线性叠加 → 归一化防 clipping。

#### 2.10.3 数据架构

**数据持有（内存）：** 混音配置。

**数据依赖：** 无。

---

## 三、POC 实现策略

### 3.1 各模块 POC 实现方式

| 模块 | POC 实现 | 说明 |
|:----:|----------|------|
| **M1 Gateway** | ✅ 完整实现 | WS + gRPC 双向流 |
| **M2 Session** | ✅ 完整实现 | 内存 dict 会话存储（生产规划: Redis） |
| **M3 Text Preproc** | ⚠️ 简化实现 | 仅 HTML 清洗 + 基本数字转写。正则规则引擎 |
| **M4 Linguistic** | ⚠️ 简化实现 | 调用 TTS 模型内置 G2P，不独立部署 Prosody 模型 |
| **M5 Emotion** | ⚠️ Mock 实现 | 默认返回 `neutral(1.0)`。接口保留，不调 LLM |
| **M6 Speaker** | ⚠️ 逻辑完整，数据简化 | CRUD + JSON 文件存储。Embedding 和 Prompt Audio 返回空占位符 |
| **M7 TTS Engine** | ❌ Mock 实现 | **正弦波生成器**（非真实语音合成）。按 Emotion 选择正弦波频率/音量。待集成 CosyVoice2 / FishSpeech |
| **M8 DSP** | ⚠️ 简化实现 | 仅 Normalize + Silence Trim，不做 Noise Reduction |
| **M9 Cache** | ✅ 接口完整，存储简化 | 内存 dict 缓存（生产规划: Redis） |
| **M10 Mixer** | ❌ 暂不实现 | POC 仅合成单音轨人声。接口保留 |

### 3.2 POC 管线数据流

```
客户端 text
  │
  ▼
M1 Gateway → 创建 M2 Session
  │
  ▼
M3: text ──→ normalized_text  (pass-through / 简单 TN)
  │
  ├─→ M5: emotion_tag  (固定 neutral)
  │
  ▼
M4: normalized_text + emotion_tag ──→ linguistic_features  (模型内置 G2P)
  │
  ├─→ M6: speaker_embedding (音色加载)
  │
  ▼
M7: linguistic_features + emotion_tag + speaker_embedding
  │
  ├─→ 查 M9 Cache
  │     ├─ 命中 → 直接返回
  │     └─ 未命中 → 模型推理
  │
  ├─→ M8: PCM → 后处理 (Normalize + Trim)
  │
  └─→ M1: 逐 chunk 推送给客户端
```

### 3.3 POC 验证场景

| # | 场景 | 操作 | 预期结果 |
|:-:|------|------|----------|
| V1 | **WS 流式合成** | 客户端 → `synthesis_request{text:"你好"}` | 收到 N 个 `audio_chunk`，最后 `synthesis_complete`，PCM 可播放 |
| V2 | **gRPC 双向流** | gRPC → `SynthesizeRequest{text:"欢迎"}` | stream 返回 N 个 `AudioChunk` + `SynthesisComplete` |
| V3 | **取消合成** | synthesis_request 后立即 cancel | ⚠️ POC 仅记录 cancel 日志，不会中止合成（生产需实现） |
| V4 | **缓存命中** | 同一文本合成两次 | 第二次首包延迟 < 5ms |
| V5 | **会话超时** | WS 连接 30s 不发送消息 | 服务端主动断开 |
| V6 | **音色切换** | 两次不同 voice_id | 两段音频音色不同 |
| V7 | **完整管线** | text="今天是2026年7月13日，😊欢迎！" | TN 正确转写日期和 Emoji，PCM 输出正常 |
| V8 | **错误处理** | 未知 voice_id | error{error_code: 3001} |
| V9 | **健康检查** | gRPC Health() | status: "healthy" |

### 3.4 代码库中本文未提及的组件

以下组件存在于仓库中，但本文未覆盖：

| 组件 | 位置 | 说明 |
|:----:|------|------|
| **浏览器测试客户端** | `static/index.html` | WebSocket 连接测试页，支持文本输入、音色/情感选择、Web Audio API 播放 |
| **启动脚本** | `scripts/start.sh` | 杀掉旧进程 → `python3 -m src.main` |
| **安装脚本** | `scripts/install.sh` | pip 安装依赖 + 生成 gRPC stubs |
| **端到端测试** | `tests/test_e2e.py` | 覆盖 V1–V9 验证场景，session 级 fixture 自动起停服务 |
| **音色 JSON 持久化** | `voices/{voice_id}/voice.json` | 通过 REST API 创建的音色持久化为 JSON 文件 |
| **Emotion→音频映射** | `tts_engine.py:EMOTION_AUDIO_MAP` | 正弦波 Mock 中 emotion 到频率/音量的映射表 |

---

## 四、POC 代码与架构文档的关键差异总结

| 差异点 | Architecture.md 原始描述 | 实际代码 | 严重程度 |
|:-------|:-------------------------|:---------|:---------|
| M7 TTS Engine | "CosyVoice2 推理" | 正弦波生成器 | ❌ 高 |
| M7 管线所有权 | M7 内部编排 M3/M4/M5/M6 | 由 main.py Pipeline Runner 编排 | ⚠️ 中 |
| M6 数据存储 | PostgreSQL + MinIO | JSON 文件 | ⚠️ 中 |
| M6 Embedding | 返回 numpy 向量 | 返回空列表 `[]` | ⚠️ 中 |
| M9 数据存储 | Redis | 内存 dict | ⚠️ 低 |
| M2 数据存储 | Redis | 内存 dict | ⚠️ 低 |
| M2 空闲超时 | 30min | 30s | ⚠️ 低 |
| M3 量词/单位 | 文档有但未实现 | 代码不存在 | ⚠️ 低 |
| Cancel | "合成中途停止" | 仅记录日志 | ⚠️ 低 |
| 浏览器客户端/脚本/测试 | 未提及 | 仓库中存在 | ℹ️ 遗漏 |
