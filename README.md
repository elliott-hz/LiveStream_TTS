# 企业级 TTS 平台架构设计

> ⚠️ **本文档描述的是目标架构（Target Architecture）**，即项目希望演进到的最终形态，并非当前实现。
> 当前 **POC 阶段** 的实际实现请详见 [`Architecture.md`](Architecture.md) 第 3 节（POC 实现策略），
> 或直接阅读 [`src/`](src/) 目录下的源代码。
>
> 下表快速对照当前实现与目标架构的差距：

| 能力 | 目标架构 | POC 当前实现 |
|:-----|:---------|:-------------|
| TTS 引擎 | CosyVoice2 / FishSpeech | 正弦波 Mock（无真实语音合成） |
| 音色存储 | PostgreSQL + MinIO | JSON 文件（voices/ 目录） |
| 音频缓存 | Redis | 内存 dict |
| 会话存储 | Redis | 内存 dict |
| 流式传输 | WebRTC / RTMP / HLS | 裸 WebSocket + PCM |
| 消息队列 | Kafka / RabbitMQ | 无 |
| 监控 | Prometheus + Grafana | 无 |
| 容器化 | Docker + Kubernetes | 无 |
| ML 推理优化 | ONNX / TensorRT / INT8 | 无 |
| 认证 / 限流 | Auth + Rate Limit | 无 |

> 站在 **企业级 AI 数字人 / AI Agent / AI 客服** 的角度，一个真正可商用的 TTS 平台，已经不是单个模型，而是一个完整的**语音生成平台（Speech Generation Platform）**。
>
> 一般拆成 **8~10 个微服务**。

---

## 总体架构

```text
                           AI Agent / LLM
                                  │
                                  ▼
                    ┌────────────────────────┐
                    │   TTS Gateway API      │
                    │ REST / WebSocket / gRPC│
                    └──────────┬─────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
        Text Preprocessor   Session Manager   Auth / Rate Limit
        (含 TN)                  │
                │                │
                ▼                │
      ┌──────────────────┐       │
      │ Text Normalizer  │       │
      │ (数字/日期/货币/  │       │
      │  URL/Emoji...)   │       │
      └────────┬─────────┘       │
               ▼                 ▼
      ┌──────────────────┐
      │  Linguistic      │  ← 注入 Emotion Tag
      │  Processing      │◄───────────────┐
      │  Engine          │                │
      │  (G2P/Prosody/   │                │
      │   停顿/重音)      │                │
      └────────┬─────────┘                │
               ▼                          │
      ┌──────────────────┐                │
      │  Emotion & Style │                │
      │  Engine          │────────────────┘
      │  (LLM 驱动       │
      │   情绪/风格分类)   │
      └────────┬─────────┘
               ▼
 Speaker Manager
 (Voice Profile / Clone)
      │
      ▼
 Streaming TTS Engine
 (CosyVoice2 / FishSpeech)
      │
      ▼
 Audio Post Processing
      │
      ├──────────────┐
      ▼              ▼
 Audio Cache     Audio Mixer
      │              │
      └──────┬───────┘
             ▼
 Streaming Output
(WebRTC / PCM / Opus / RTMP)
             │
             ▼
 Digital Human / APP
```

整个系统分为 **输入层 → 文本理解层 → 情感层 → 声音生成层 → 音频增强层 → 输出层** 六大层次。

---

## 第一层：API Gateway（API 网关）

**职责：** 统一入口，支持多种协议。

- **REST** — 普通 APP 调用（`POST /api/v1/tts`）
- **WebSocket** — 数字人流式输出（`/ws/v1/tts`）
- **gRPC** — Agent 内部高速通信（`tts.v1.TTS/Streaming`）

---

## 第二层：Text Preprocessor（文本预处理）

很多人以为 LLM 输出直接送 TTS 即可，但企业不会。例如 `2026/07/10` 需要转为 `二零二六年七月十日`。

这一层的核心子模块是 **Text Normalizer（TN）**，负责将原始文本转为适合朗读的规范形式。

### Text Normalizer（文本规范化器）

**输入：** LLM / Agent 输出的原始文本
**输出：** 规范化后的纯文本
**性质：** 纯 text→text 转换，不涉及语音学

#### 子模块拆分

| 子模块 | 职责 | 示例 |
|--------|------|------|
| **数字转写** | 阿拉伯数字 → 中文数字读法 | `123456` → `十二万三千四百五十六` |
| **货币转写** | 货币符号 + 数字 → 金额读法 | `￥1999` → `一千九百九十九元` |
| **日期/时间转写** | 数字日期 → 自然语言日期 | `2026-07-10` → `二零二六年七月十日` |
| **URL/Email 转写** | 链接 → 可读域名/地址 | `www.example.com` → `三达不溜点 example 点 com` |
| **Emoji 转写** | 表情符号 → 文字描述 | `😊` → `微笑` |
| **特殊符号清洗** | HTML 标签、Markdown 标记、控制字符 | `<b>标题</b>` → `标题` |
| **量词/单位转写** | 科学单位、缩写 → 标准中文 | `100km/h` → `一百公里每小时` |
| **电话号码转写** | 数字分段朗读 | `138xxxx` → `幺三八 ...`（按业务场景选择逐位/分段） |

#### 工程实现要点

- **规则引擎 + ML 混合：** 正则匹配常见格式 + 基于 CRF / BERT 的上下文感知转写用于模糊场景
- **上下文消歧：** `2026` 可能是年份也可能是一串数字，需要 LLM 输入中携带 Context Mark
- **可配置规则表：** 不同行业（金融 / 电商 / 客服）有不同的数字读法偏好，规则需支持热加载
- **流水线顺序敏感：** 先处理 HTML/Markdown 清洗 → 再处理 Emoji → 最后处理数字/日期/货币，避免混淆

> **❌ 常见误区：** TN 不属于 Linguistic Processing Engine。TN 是**纯文本层面的规范化**（text→text），不涉及语音学。Linguistic Engine 是在 TN 完成后的规范化文本上做 G2P / Prosody 等语音学处理。

---

## 第三层：Linguistic Processing Engine（语言处理引擎）

在 TN 完成后的规范化文本上做语音学处理。核心能力：

- G2P（Grapheme-to-Phoneme，字音转换）
- 分词（Word Segmentation）
- 断句（Sentence Boundary Detection）
- **Prosody 预测**（停顿时长、Pitch 曲线、语速变化）
- 重音（Stress）
- 拼音标注（Pinyin）
- 英文与缩写处理

**示例：** `AI Agent-native SDLC` 不会逐字读 "A I"，而是按语义读作 "AI Agent Native Software Delivery"。

**Prosody 预测示例：**
```
你好，             → Pause 300ms
欢迎来到直播间。     → Stress + Pitch 上扬
```

> **注意：** TN（纯文本规范化）和 Emotion（情感分类）**不**属于这一层。Emotion 独立成层后，通过 Emotion Tag 注入到 Linguistic Engine，影响 Prosody 的生成参数。

### 输出（送入 Streaming TTS Engine）

| 输出数据 | 格式 | 说明 |
|----------|------|------|
| **Phoneme Sequence（音素序列）** | `['b','ei','j','ing','h','uan','y','ing',...]` | 最核心输出，告诉 TTS 模型要发什么音 |
| **Duration（音素时长）** | `[120ms, 80ms, 90ms, ...]` | 每个音素持续多久 |
| **F0 Contour（基频曲线）** | 连续浮点序列 | Pitch 随时间的走向，决定语调（疑问/陈述） |
| **Pause Positions（停顿位置）** | `{pos: 7, duration: 300ms}` | 哪里停顿、停多久 |
| **Energy Contour（能量包络）** | 连续浮点序列 | 响度/重音的变化曲线 |

这些输出统称为 **Acoustic Features（声学特征）**，是 Linguistic Engine 给 TTS Engine 的"发音乐谱"。

---

## 第四层：Emotion & Style Engine（情感与风格引擎）

**独立于 Linguistic Engine 的单独一层。** Emotion 不是语音学问题，而是一个高层语义决策——通常由 LLM 或独立的分类模型完成。

**职责：** 分析文本语义，输出情感/风格标签，注入到 Linguistic Engine 和 Speaker Manager，影响 Prosody 和音色选择。

企业级 TTS 一定会支持多情感。

| 场景 | 情感 |
|------|------|
| 客服 | 温和、平静 |
| 直播带货 | 兴奋、激昂 |
| 新闻播报 | 严肃、正式 |
| 儿童内容 | 可爱、活泼 |
| 语音助手 | 亲切、自然 |

**情感类型与强度：**
```
Happy: 0.8    Serious: 0.6    Excited: 0.9
Cute: 0.7     Sad: 0.4         Calm: 0.5
```

---

## 第五层：Speaker Manager（音色管理器）

声音管理中心，存储所有音色配置。

**保存内容：**
- `voice_id` — 音色唯一标识
- `speaker_id` — 说话人标识
- `embedding` — 音色向量
- `prompt_audio` — 参考音频

**声音克隆流程：**
```
30秒录音 → Embedding 提取 → 保存到 Speaker Manager
之后调用：speaker_id=elliott 即可使用该音色
```

**支持的音色：** 主播 A/B、客服、CEO、男声/女声/童声

---

## 第六层：Streaming TTS Engine（流式 TTS 引擎 — 核心）

**这是真正的语音合成步骤。** 前面所有层（TN、Linguistic、Emotion、Speaker Manager）都是在为这一步准备输入数据。

### 输入全景

```text
┌─ Linguistic Engine ────────────────────┐
│  Phoneme Sequence (音素序列)            │
│  Duration (音素时长)                     │
│  F0 Contour (基频曲线)                   │
│  Pause Positions (停顿时长)             │
│  Energy Contour (能量/响度)             │
└────────────────────┬────────────────────┘
                     │
┌─ Emotion & Style ──┤
│  Emotion Tag       │  ← 影响 prosody 参数
│  Style Tag         │
│  Intensity         │
└────────────────────┘
                     │
┌─ Speaker Manager ──┤
│  Speaker Embedding │  ← 确定音色身份
│  (voice_id)        │
│  Prompt Audio      │  ← 零样本参考音频（可选）
└────────────────────┘
                     ▼
      ┌─────────────────────────┐
      │  Streaming TTS Engine   │
      │  (CosyVoice2 / FishSpeech)
      └────────────┬────────────┘
                   ▼
         Streaming PCM Chunks
```

**三条输入流的角色：**

| 输入来源 | 携带信息 | 作用 |
|----------|----------|------|
| **Linguistic Engine** | 音素序列 + 时长 + F0 + 停顿 | **说什么、怎么发音** — 内容的骨架 |
| **Speaker Manager** | Speaker Embedding / Prompt Audio | **谁在说** — 音色身份，确定声纹特征 |
| **Emotion & Style** | Emotion Tag + Intensity | **什么情绪在说** — 影响语气、语速、语调曲线 |

> 三条输入缺一不可。少了 Speaker Embedding → 不知道用谁的声音；少了 Emotion Tag → 声音平淡无情感；少了 Linguistic Features → 不知道怎么发音。

### 输出

| 属性 | 说明 |
|------|------|
| **格式** | 流式 PCM Chunk，每 20ms / 40ms / 80ms 持续输出 |
| **采样率** | 16kHz / 24kHz / 48kHz（取决于模型和场景） |
| **编码** | PCM（原始）→ 后续由 Streaming Server 转 Opus / AAC 等 |
| **延迟** | 首包延迟 < 200ms（业界目标），Chunk 间隔稳定 |

### 模型需要微调吗？

| 场景 | 是否需要微调 | 理由 |
|------|-------------|------|
| 通用场景，标准音色 | ❌ 不需要 | CosyVoice2 / FishSpeech 零样本效果已很好，只需提供 Prompt Audio |
| 固定一个专属音色 | ⚠️ 不一定 | 用 Speaker Encoder 做一次 Voice Clone 即可，比微调成本低得多 |
| 特定领域术语多（金融/医疗） | ✅ 建议 LoRA | 微调 Prosody 让模型更懂领域词汇的重音和停顿 |
| 需要特定情感表现力 | ✅ 建议 LoRA | 微调情感 Embedding 使情感控制更精确 |
| 多语种混合（中英夹杂） | ✅ 建议 SFT | 提升 Code-Switching 场景的发音自然度 |

**企业最佳实践：** 先用 Speaker Encoder 做 Voice Clone（成本低），效果不够再加 LoRA 微调。很少需要 Full Fine-Tuning。

### 推理优化

| 技术 | 效果 |
|------|------|
| ONNX / TensorRT 导出 | 推理速度 2-5x 提升 |
| INT8 量化 | 显存减半，速度提升 |
| KV Cache 复用 | 变长输入更高效 |
| Streaming Decode | 边合成边输出，首包延迟降低 |

**行业主流模型（2026）：**

| 模型 | 推荐指数 | 说明 |
|------|----------|------|
| **CosyVoice2** | ★★★★★ | 首选，效果最优 |
| FishSpeech | ★★★★★ | 优秀开源方案 |
| OpenVoice V2 | ★★★★☆ | 音色克隆能力强 |
| XTTS v2 | ★★★★☆ | 多语言支持好 |
| ChatTTS | ★★★★☆ | 对话场景优化 |
| MeloTTS | ★★★☆☆ | 轻量级方案 |

**企业推理优化：** TensorRT / ONNX 导出、INT8 量化、KV Cache 加速、Streaming Decode

**输出格式：** 不断输出的 PCM Chunk（每 20ms / 40ms / 80ms），而非整句合成。

---

## 第七层：Audio Post Processing（音频后处理）

### DSP 是什么？

**DSP = Digital Signal Processing（数字信号处理）。**

简单说：TTS 模型合成出来的原始音频（PCM）是"毛坯房"——可能有底噪、音量忽大忽小、首尾有静音、不同音色响度不一致等。DSP 就是对这段数字音频做一系列**数学变换**，把它变成"精装修"的成品。

好比拍完照片后做后期修图：调亮度、裁切、去噪、色彩校正。DSP 就是音频的"修图"。

### DSP 流水线

```
TTS 原始 PCM
       │
       ▼
Noise Reduction    → 降噪（去底噪、电流声）
Normalize          → 响度归一化（所有音色统一音量）
Limiter            → 限幅（防止破音/clipping）
AGC                → 自动增益控制（动态调整音量）
Compressor         → 压缩器（压低大声、提升小声，缩小动态范围）
EQ                 → 均衡器（调音色，如增强人声清晰度）
Silence Trim       → 静音裁剪（去掉首尾多余空白）
       │
       ▼
处理后的 PCM
```

**目标：** 所有音色输出音量一致，音质稳定。通常基于 FFmpeg 或 WebRTC Audio Processing 实现。

---

## 第八层：Audio Cache（音频缓存）

**场景：** 每天 `"欢迎来到直播间"` 说 100 万遍，不需要每次都重新生成。

```
hash(text) → Redis → wav
```

命中直接返回，大幅降低 GPU 推理成本。

---

## 第九层：Audio Mixer（音频混音器）

数字人场景通常包含多层音频：

| 音轨 | 音量 |
|------|------|
| 主播人声 | -12dB |
| 背景音乐（BGM） | -25dB |
| 礼物音效 | -8dB |
| 提示音 | -10dB |

所有音轨统一混音后输出。

---

## 第十层：Streaming Server（流媒体服务器）

| 输出格式 | 目标平台 |
|----------|----------|
| PCM / Opus | APP（WebSocket） |
| AAC | 通用播放 |
| WebRTC | 浏览器 |
| RTMP | OBS / 直播平台 |
| HLS | 视频点播 |

---

## 企业数据库设计

| 存储 | 技术选型 | 数据内容 |
|------|----------|----------|
| 关系库 | PostgreSQL | Voice, Speaker, Style, Emotion, History |
| 缓存 | Redis | Audio Cache, Session, Streaming Queue |
| 对象存储 | OSS / S3 / MinIO | wav, mp3, embedding, prompt_audio |

---

## GPU 推理

**推荐 GPU：** NVIDIA L40S / L20 / A10（性价比） | A100 / H20（大规模） | 4090（开发测试）

**推理框架：** LLM → vLLM / TensorRT-LLM；TTS → ONNX Runtime / TensorRT

---

## 推荐技术选型（2026）

| 模块 | 推荐方案 | 可替代方案 |
|------|----------|------------|
| API Gateway | FastAPI + gRPC + WebSocket | Spring Boot、Go Gin |
| Text Normalization | WeTextProcessing（NVIDIA）+ 自定义规则 | NeMo TN、自研 TN |
| Linguistic Processing | pypinyin + jieba + OpenCC + 自定义 Prosody | PaddleSpeech Frontend |
| Emotion / Style | LLM 预测 Emotion Tag + Prompt Style | 独立情绪分类模型 |
| Speaker Manager | PostgreSQL + Redis + Speaker Embedding | Milvus（Embedding 检索） |
| Voice Clone | CosyVoice2 Speaker Encoder | OpenVoice V2、FishSpeech |
| Streaming TTS Engine | **CosyVoice2（首选）** | FishSpeech、XTTS v2 |
| 推理优化 | ONNX Runtime + TensorRT + INT8 | TensorRT-LLM（部分场景） |
| Audio DSP | FFmpeg + WebRTC Audio Processing | SoX、RNNoise |
| Audio Cache | Redis + MinIO | S3、OSS |
| 消息队列 | Kafka / RabbitMQ | Redis Streams |
| Streaming Server | WebRTC + LiveKit | Janus、mediasoup |
| 数字人渲染 | LiveTalking + MuseTalk / Wav2Lip | SadTalker、ER-NeRF |
| 监控 | Prometheus + Grafana | ELK、OpenTelemetry |

---

## DataClaw 数字人平台推荐架构

如果这是 **DataClaw Digital Human Platform**，建议采用以下分层架构（模块解耦，各层可独立替换）：

```text
LLM / Agent Runtime
        │
        ▼
TTS Gateway（REST / WebSocket / gRPC）
        │
        ▼
Text Preprocessor（TN：数字、日期、英文、Emoji）
        │
        ▼
Linguistic Engine（G2P、Prosody、停顿、重音）
        │
        ▼                              ─┐
Emotion & Style Engine  ◄── LLM 预测 ───┤  ← 独立层
（情绪、语速、语气、角色）                  ─┘
        │
        ▼
Speaker Manager（音色管理、声音克隆、Embedding）
        │
        ▼
Streaming TTS Engine（CosyVoice2 + TensorRT）
        │
        ▼
Audio DSP（降噪、响度归一、混音）
        │
        ▼
Streaming Server（WebRTC / RTMP / PCM）
        │
        ▼
Digital Human Engine（MuseTalk / LiveTalking）
```

**架构特点：** 前端的 Agent、底层的 TTS 模型、数字人渲染都可以独立替换。例如将 CosyVoice2 换成 FishSpeech，或将 MuseTalk 升级为更先进的渲染引擎，整个系统其他部分几乎不需要改动。这也是大型企业和成熟 AI 平台普遍采用的设计思路。
