# PoC 验证架构方案

> **规模**：1 个商户 · 1-2 路同时推流
> **硬件**：1 台家用台式机 + 1 台 AutoDL 4090 GPU
> **原则**：最少依赖、最简单部署

---

## 一、物理拓扑

```
┌──────────────────────────────────────────────────┐
│                家用台式机 (Ubuntu)                  │
│                                                  │
│   uvicorn main:app  (单进程 FastAPI)              │
│   ├── SQLite          (数据存储)                  │
│   ├── 本地磁盘         (视频/音频文件)              │
│   ├── FFmpeg          (RTMP 推流到淘宝)            │
│   └── FastText/AC     (本地 CPU NLP)              │
│                                                  │
│   前端: Vite + React  (开发时独立端口)              │
└───────────────────┬──────────────────────────────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│   Public APIs    │  │ AutoDL 4090 GPU  │
│                  │  │                  │
│ DeepSeek (LLM)   │  │ Wav2Lip 口型同步  │
│ CosyVoice (TTS)  │  │ (HTTP API)       │
│ 阿里云 ASR       │  │                  │
│ 阿里云智能媒体    │  │                  │
└──────────────────┘  └──────────────────┘
```

**外部依赖仅 2 个**：Public APIs + AutoDL GPU

---

## 二、技术选型 (PoC 极简版)

| 层 | 选型 | 理由 |
|----|------|------|
| Web 框架 | FastAPI | async、WebSocket、BackgroundTasks 内置 |
| 数据库 | **SQLite** (aiosqlite) | 零配置、单文件、PoC 够用 |
| ORM | SQLAlchemy 2.0 async | 后续可无缝切 PostgreSQL |
| 文件存储 | **本地磁盘** (`./data/videos/`) | 无需 MinIO，PoC 只有 1 台机器 |
| 异步任务 | **FastAPI BackgroundTasks** | 代替 Celery，单进程搞定 |
| 向量检索 | **SQLite + 关键词匹配** | PoC 不装 Milvus，先跑通流程 |
| NLP | FastText + AC 自动机 (本地 CPU) | 10MB 模型，毫秒级 |
| 弹幕通信 | **内存 dict + asyncio.Queue** | 单进程内 pub/sub，无需 Redis |
| 前端 | **Vite + React 18 + TypeScript** | 工程化 SPA |
| 流媒体 | FFmpeg (系统安装) | RTMP 推流 + 音频混流 |

> 一句话：**装上 Python 3.12 + FFmpeg，`pip install` + `uvicorn` 就能跑。** 不需要 Docker。

---

## 三、项目目录结构

```
LiveStream_TTS/
├── backend/
│   ├── main.py                      # FastAPI 入口 + 生命周期
│   ├── config.py                    # 配置 (全部从 .env 读取)
│   │
│   ├── modules/                     # 业务模块 (每个模块 router/service/schemas)
│   │   ├── product/                 # 商品知识库
│   │   ├── video_asset/             # 视频素材库 (上传→解析→切片)
│   │   ├── live_video/              # 直播视频库 (编排)
│   │   ├── live_room/               # 直播间管理 (创建/排班/开播/停播)
│   │   ├── live_control/            # 直播中控台 (WebSocket)
│   │   ├── interaction/             # 互动设置
│   │   └── analytics/               # 数据大盘
│   │
│   ├── engine/                      # 核心引擎 (封装外部 I/O)
│   │   ├── llm.py                   # DeepSeek API
│   │   ├── tts.py                   # CosyVoice API
│   │   ├── asr.py                   # 阿里云 ASR API
│   │   ├── scene_detect.py          # 阿里云智能媒体 API
│   │   ├── wav2lip.py               # AutoDL 4090 HTTP 调用
│   │   ├── nlp.py                   # 本地: AC自动机 + FastText
│   │   └── streaming/
│   │       ├── playlist.py          # 播单计算
│   │       └── ffmpeg.py            # FFmpeg 进程管理
│   │
│   ├── models/                      # SQLAlchemy 模型
│   │   ├── base.py                  # Base + session factory
│   │   ├── product.py
│   │   ├── video.py
│   │   ├── room.py
│   │   ├── interaction.py
│   │   └── analytics.py
│   │
│   └── adapters/                    # 平台适配器
│       ├── base.py                  # 抽象接口
│       └── taobao.py                # 淘宝适配器
│
├── frontend/                        # Vite + React + TypeScript
│   ├── src/
│   │   ├── pages/                   # 7 个商户端页面
│   │   ├── components/              # 共享组件
│   │   ├── hooks/                   # 自定义 Hooks
│   │   └── api/                     # API 客户端
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
│
├── data/                            # 运行时数据 (gitignore)
│   ├── app.db                       # SQLite 数据库文件
│   └── videos/                      # 上传的视频 + 切片
│
├── .env                             # API Key 等敏感配置
├── requirements.txt
└── README.md
```

---

## 四、数据库模型 (SQLAlchemy)

```python
# ---- product.py ----
class Product(Base):
    id: UUID (pk)
    name: str            # "法式碎花连衣裙"
    sku: str             # "D001"
    category: str        # "女装"

class ProductKB(Base):   # 商品在各平台的知识库
    product_id: FK
    platform: str        # taobao / douyin
    platform_sku: str
    price: str
    detail_html: str     # 富文本详情 (AI 回复知识来源)

# ---- video.py ----
class RawVideo(Base):
    file_path: str       # 本地路径
    duration: int        # 秒
    parse_status: str    # pending / processing / done

class VideoSegment(Base):  # AI 解析后的切片
    raw_video_id: FK
    start_time: float
    end_time: float
    product_id: FK
    script: str          # 提取的讲解文本
    status: str          # pending / published

class LiveVideo(Base):     # 编排好的直播视频
    name: str
    play_mode: str       # sequential / random

class LiveVideoClip(Base): # 编排中的切片项
    live_video_id: FK
    segment_id: FK
    sort_order: int
    weight: int          # 1-5

# ---- room.py ----
class LiveRoom(Base):
    name: str
    platform: str        # taobao
    rtmp_url: str        # 淘宝推流地址
    status: str          # idle / live
    attached_video_id: FK(LiveVideo)

class RoomSchedule(Base):
    room_id: FK
    enabled: bool
    start_time: time
    end_time: time

# ---- interaction.py ----
class InteractionConfig(Base):
    reply_mode: str      # tts / original_audio
    reply_style: str     # warm / professional / lively
    tts_speed: float
    tts_volume: float

class ReplyTemplate(Base):
    product_id: FK
    keywords: str
    reply_text: str

# ---- analytics.py ----
class LiveSession(Base):
    room_id: FK
    start_time: datetime
    end_time: datetime

class DanmakuRecord(Base):
    session_id: FK
    user_name: str
    content: str
    type: str            # comment / question / order_intent
    ai_reply: str
```

---

## 五、核心数据流

### 5.1 视频解析 (BackgroundTasks)

```python
# modules/video_asset/router.py
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_video(file: UploadFile, bg: BackgroundTasks):
    # 1. 保存到本地磁盘
    path = f"data/videos/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    # 2. 写 DB (status=pending)
    video = RawVideo(file_path=path, parse_status="pending")
    db.add(video); await db.commit()

    # 3. 丢到后台慢慢解析
    bg.add_task(parse_video_pipeline, video.id, path)
    return {"video_id": video.id, "status": "pending"}

# engine 目录下的解析管线 (被 BackgroundTasks 调用)
async def parse_video_pipeline(video_id: UUID, path: str):
    # Step 1: ASR → 阿里云 API
    transcript = await asr.transcribe(path)
    # Step 2: 场景检测 → 阿里云智能媒体 API
    segments = await scene_detect.detect(path)
    # Step 3: 脚本清洗 → DeepSeek
    for seg in segments:
        seg["script"] = await llm.clean_script(seg["raw_text"])
    # Step 4: FFmpeg 无损切割
    for seg in segments:
        seg["clip_path"] = ffmpeg.cut(path, seg["start"], seg["end"])
    # Step 5: 写入 DB (status=done)
    ...
```

### 5.2 直播推流 (FFmpeg 子进程)

```
开播指令
  → playlist.py: 按权重+模式算出播放顺序
  → ffmpeg.py: subprocess.Popen([
        "ffmpeg",
        "-f", "concat",
        "-i", "playlist.txt",     # 切片播放列表
        "-c", "copy",
        "-f", "flv",
        rtmp_url                   # 淘宝推流地址
    ])
  → 循环播放, 直到停播 → process.terminate()
```

### 5.3 AI 互动 (弹幕 → 回复)

```
淘宝弹幕 (adapter/taobao.py 轮询/WS)
  → nlp.py:
      Stage 1: AC自动机 敏感词过滤 → 命中则丢弃
      Stage 2: FastText 意图分类 → 闲聊不回复 / 提问继续
  → 5秒批处理 + 同类去重
  → 关键词匹配商品知识库 (SQLite LIKE / simple FTS)
  → llm.py: DeepSeek API → 生成文字回复
  → 文字回复发到淘宝聊天区 (adapter/taobao.py)
  → (可选) tts.py: CosyVoice API → 语音
  → (可选) wav2lip.py: AutoDL 4090 → 口型帧
  → ffmpeg.py: 混入推流音频
```

---

## 六、API 设计

RESTful，带模块前缀：

```
# 商品知识库
GET    /api/products
POST   /api/products
GET    /api/products/{id}
POST   /api/products/import          # AI 导入

# 视频素材库
GET    /api/video-assets
POST   /api/video-assets/upload      # 上传 + 触发解析
GET    /api/video-assets/{id}/segments

# 直播视频库 (编排)
GET    /api/live-videos
POST   /api/live-videos
PUT    /api/live-videos/{id}/clips   # 调整编排

# 直播间管理
GET    /api/live-rooms
POST   /api/live-rooms
POST   /api/live-rooms/{id}/start    # 开播
POST   /api/live-rooms/{id}/stop     # 停播

# 直播中控台
WS     /ws/live/{room_id}            # 实时弹幕 + 指标 + 控制

# 互动设置
GET    /api/interaction/config
PUT    /api/interaction/config

# 数据大盘
GET    /api/analytics/sessions/{id}
GET    /api/analytics/product-material
GET    /api/analytics/product-live
```

---

## 七、配置 (.env)

```bash
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# 文件存储
VIDEO_DIR=./data/videos

# LLM
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# TTS
COSYVOICE_API_KEY=xxx

# 阿里云
ALIYUN_ACCESS_KEY=xxx
ALIYUN_SECRET=xxx

# AutoDL GPU
WAV2LIP_URL=http://12.34.56.78:8000

# 淘宝开放平台
TAOBAO_APP_KEY=xxx
TAOBAO_APP_SECRET=xxx
```

---

## 八、启动方式

```bash
# 台式机上:
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端开发:
cd frontend
npm install
npm run dev          # Vite dev server → localhost:5173
```

---

## 九、渐进路线

| 阶段 | 交付物 |
|------|--------|
| **W1-2** | SQLite 建表 + 商品CRUD + 视频上传 → 阿里云API解析 → 切片入库 |
| **W3-4** | FFmpeg 播单 → RTMP 推到淘宝 + 直播间管理 |
| **W5-6** | 弹幕采集 → NLP 分类 → DeepSeek 文字回复 → 淘宝发消息 |
| **W7-8** | TTS 语音 + Wav2Lip 口型 → 混入推流 |
| **W9-10** | React 前端 + 全链路联调 |

---

## 十、明确不做

- ❌ 不装 Docker — 直接 uvicorn + npm dev
- ❌ 不装 PostgreSQL / Redis / Milvus / MinIO
- ❌ 不用 Celery — FastAPI BackgroundTasks 足够
- ❌ 不拆微服务 — 单进程
- ❌ 不搞 gRPC — 全 HTTP/JSON
