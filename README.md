# 数字人直播带货平台 — Digital Human Livestream Shopping Platform

> **Monorepo | 16 微服务 | Python 3.11 FastAPI | gRPC + Kafka | ~500 测试**

面向国内电商环境的数字人直播带货 SaaS 平台，为商家提供从"选品、形象定制、脚本生成、直播间搭建、多平台推流、实时互动到数据分析"的全链路服务。

---

## 架构总览

### 16 微服务 · 四大领域

| 领域 | 服务 (16) | 职责 |
|------|-----------|------|
| **核心业务** | `gateway-svc`, `user-svc`, `product-svc`, `script-svc`, `live-mgr-svc`, `avatar-svc`, `voice-svc`, `knowledge-svc` | 网关、用户、商品、脚本、直播间、形象、音色、知识库 |
| **AI 能力** | `tts-svc`, `nlp-svc`, `render-svc` | 语音合成、LLM 对话、数字人渲染 |
| **平台数据** | `interact-svc`, `platform-sync-svc`, `analytics-svc`, `billing-svc`, `audit-svc` | 互动、多平台同步、分析、计费、审计 |
| **基础设施** | `stream-svc`, `profile-svc` | 流媒体推流、用户画像引擎 |

### 通信方式

- **gRPC + Protobuf** — 服务间同步调用，`libs/proto/` 集中管理 18 个 proto 定义
- **Kafka (aiokafka)** — 异步事件驱动：弹幕、互动、状态变更
- **FastAPI HTTP** — 对外 REST API（通过 gateway-svc 统一暴露）
- **WebSocket** — 流式 TTS 音频输出、弹幕推送

### 数据存储

| 存储 | 用途 |
|------|------|
| **PostgreSQL 15** (TimescaleDB) | 核心业务数据（用户、商品、脚本、直播间） |
| **Redis 7** | 缓存、Session、实时画像热数据 |
| **Kafka** | 消息队列、事件流 |
| **MinIO** (S3 兼容) | 对象存储：音频、视频、模型文件 |
| **Milvus** (Phase 2) | 向量数据库：Embedding 检索 |
| **Elasticsearch 8** (Phase 2) | 日志聚合、全文搜索 |

---

## 技术栈

| 类别 | 选型 |
|------|------|
| **语言/框架** | Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.0 async |
| **服务通信** | gRPC, Protobuf, aiokafka |
| **数据库** | PostgreSQL 15 + TimescaleDB, Redis 7, Milvus (Phase 2) |
| **AI 引擎** | DeepSeek API / Qwen LLM, CosyVoice2 (Phase 2), Wav2Lip |
| **容器与编排** | Docker, Kubernetes (Kustomize), Istio (Phase 2) |
| **GitOps** | ArgoCD (Phase 2) |
| **可观测性** | Prometheus + Grafana, Jaeger, ELK |
| **工具链** | Ruff (linter), Black (formatter), MyPy, Pytest, Coverage |

---

## 项目结构

```
LiveStream_TTS/
├── services/                 # 16 个微服务，每个独立可部署
│   ├── gateway-svc/          #   API 网关
│   ├── user-svc/             #   用户中心
│   ├── product-svc/          #   商品服务
│   ├── script-svc/           #   脚本服务
│   ├── live-mgr-svc/         #   直播间管理
│   ├── avatar-svc/           #   数字人形象
│   ├── voice-svc/            #   音色服务
│   ├── knowledge-svc/        #   知识库
│   ├── tts-svc/              #   语音合成
│   ├── nlp-svc/              #   自然语言
│   ├── render-svc/           #   数字人渲染
│   ├── interact-svc/         #   互动事件
│   ├── platform-sync-svc/    #   平台同步
│   ├── analytics-svc/        #   数据分析
│   ├── billing-svc/          #   计费服务
│   └── audit-svc/            #   审计合规
├── libs/                     # 共享库
│   ├── common/               #   通用工具（配置、日志、错误码）
│   ├── db/                   #   数据库会话模型
│   ├── kafka/                #   Kafka 生产/消费封装
│   ├── proto/                #   Protobuf 定义 + 生成代码（18个服务）
│   └── testing/              #   测试夹具与工具
├── deploy/                   # 部署配置
│   ├── docker/               #   Dockerfile 模板 + 初始化脚本
│   └── k8s/                  #   Kubernetes 清单（base + overlays）
├── docs/                     # 架构文档
├── scripts/                  # 编译脚本（compile_protos.sh）
├── static/                   # 调试用 TTS 前端页面
├── docker-compose.yml        # 本地开发基础设施
└── pyproject.toml             # 项目级工具配置
```

---

## 快速开始

### 前置依赖

- Python 3.11+
- Docker & Docker Compose
- `make` (可选)

### 启动基础设施

```bash
docker compose up -d
# 启动: PostgreSQL 15, Redis 7, Kafka, MinIO
# Phase 2 附加: docker compose --profile phase2 up -d (Milvus, ES)
```

### 运行单个服务

```bash
cd services/user-svc
pip install -r requirements.txt
python src/main.py
```

### 运行所有测试

```bash
python -m pytest services/ -x
# 或使用 tox
tox
```

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [PRD 需求文档](docs/PRD-数字人直播带货平台-需求文档.md) | 产品定义、业务场景、功能规格 |
| [架构设计](docs/Architecture-数字人直播平台-工业级架构设计.md) | 七层架构、微服务设计、数据流 |
| [竞品对比与差异化分析](docs/竞品对比与差异化分析.md) | 特看/元真/Johnsmith/VSO 对比 |
| [开发执行计划](docs/代码开发执行计划.md) | Phase 1-3 分期规划与排期 |

---

## 开发路线

| 阶段 | 状态 | 核心交付 |
|------|------|---------|
| **Phase 1 — MVP 骨架** | ✅ 完成 | 16 微服务脚手架、gRPC 通信、Kafka 事件流、CI/CD、~500 测试 |
| **Phase 2 — AI 集成** | 🔄 进行中 | CosyVoice2 情感 TTS、Wav2Lip 口型同步、自部署 LLM (Qwen)、Istio 服务网格、ArgoCD GitOps |
| **Phase 3 — 生产加固** | 📋 计划中 | GPU 推理优化、多 AZ 高可用、全链路监控告警、安全合规认证 |

---

## 许可

本项目为私有仓库，内部使用。
