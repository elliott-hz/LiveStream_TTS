# LiveStream TTS — 数字人直播带货 SaaS 平台

> Monorepo | 16 microservices | Python 3.11 FastAPI | gRPC + Kafka | ~500 tests
>
> 面向国内电商环境的 AI 数字人直播带货平台。数字人 7×24 小时直播，听懂弹幕、生成回复、情感 TTS 播报、口型同步、RTMP 推流。

## 技术栈

| 层 | 技术 |
|---|---|
| 语言 | **Python 3.11** (全部服务) |
| HTTP | FastAPI + Uvicorn |
| 服务间通信 | **gRPC** (同步调用) + **Kafka** (异步事件) |
| 数据库 | PostgreSQL 15 + TimescaleDB, Redis 7 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| 对象存储 | MinIO (S3 兼容) |
| 向量数据库 | Milvus (Phase 2) |
| AI 模型 | CosyVoice2 (TTS), Wav2Lip (口型), Qwen-3-7B (LLM), 0.5B 小模型 (NLP) |
| 容器化 | Docker (multi-stage) + K8s (Kustomize overlays) |
| CI/CD | GitHub Actions |

## 项目结构

```
LiveStream_TTS/
├── services/          # 16 个微服务 (每个独立部署)
│   ├── gateway-svc/   # API 网关: JWT, 限流, gRPC 代理
│   ├── user-svc/      # 用户中心: 注册/登录, RBAC, 店铺管理
│   ├── product-svc/   # 商品 CRUD
│   ├── script-svc/    # 直播脚本生成
│   ├── live-mgr-svc/  # 直播间管理, 状态机
│   ├── avatar-svc/    # 数字人形象管理 + 克隆任务
│   ├── voice-svc/     # 音色管理 + 克隆任务
│   ├── knowledge-svc/ # 知识库 RAG
│   ├── tts-svc/       # TTS 引擎: CosyVoice2 + 情感引擎 + DSP
│   ├── nlp-svc/       # NLP: 意图/情感/敏感词 (CPU)
│   ├── render-svc/    # 画面渲染: Wav2Lip + BlendShape + 合成
│   ├── interact-svc/  # 实时互动管线: 弹幕→LLM→TTS→渲染
│   ├── platform-sync-svc/ # 多平台适配 (抖音/淘宝/京东)
│   ├── analytics-svc/ # 数据分析
│   ├── billing-svc/   # 计费 + 用量
│   ├── audit-svc/     # 审计日志
│   ├── stream-svc/    # RTMP/SRT 推流 + FFmpeg
│   └── profile-svc/   # 用户画像 (实时特征)
├── libs/              # 5 个共享库
│   ├── common/        # 配置, 错误码, 日志(structlog), gRPC 工具
│   ├── db/            # SQLAlchemy async session 工厂
│   ├── kafka/         # aiokafka producer/consumer 封装
│   ├── proto/         # 19 个 protobuf 定义 + 生成桩代码
│   └── testing/       # 测试 fixtures, 假数据生成器
├── deploy/            # K8s Kustomize (base + dev/staging/prod overlays)
├── docs/              # PRD, 架构设计, 开发计划, Phase2 计划, 竞品分析
├── specs/             # 开发规范 (分支管理, 代码风格, Commit, Review)
├── scripts/           # Proto 编译脚本
├── static/            # TTS 调测前端 (index.html)
└── docker-compose.yml # 本地开发基础设施 (PG, Redis, Kafka, MinIO, Milvus, ES)
```

## 架构核心概念

### 通信模式
- **gRPC**: 同步 service-to-service 调用, 19 个 proto 服务定义在 `libs/proto/`
- **Kafka**: 异步事件流 (弹幕采集→处理→回复, 直播状态变更, 审计日志等)
- **FastAPI HTTP**: 外部 REST API (通过 gateway-svc 暴露)
- **WebSocket**: TTS 流式音频输出

### 多租户
- 租户 = `Store` (店铺)
- 所有核心实体带 `store_id` 外键
- JWT token 包含 `store_id`, gateway 代理自动注入
- RBAC 角色: `merchant_admin/editor/viewer` (租户级) + `super_admin` (平台级)

### 实时互动管线 (核心运行时)
```
弹幕 → interact-svc → nlp-svc (意图/情感/敏感词)
                    → knowledge-svc (RAG 检索)
                    → llm-svc (生成回复) / DeepSeek API (降级)
                    → tts-svc (语音合成) → render-svc (口型渲染) → stream-svc (RTMP 推流)
```

### 标准微服务结构
```
services/{name}-svc/
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── k8s/               # configmap, deployment, service (hpa 可选)
├── src/
│   ├── main.py        # FastAPI + gRPC 入口
│   ├── config.py      # ServiceConfig 子类 (3 层: env > ConfigMap > default)
│   ├── api/grpc_impl.py
│   ├── http/routes.py
│   ├── models/        # SQLAlchemy ORM
│   └── services/      # 业务逻辑
└── tests/
```

## 开发规范

**所有规范在 `specs/` 目录，必须遵守：**
- `specs/01-git-branch.md` — 分支管理 (Trunk-Based, feature/fix/docs 前缀, Squash Merge)
- `specs/02-code-style.md` — 代码风格 (类型标注, 异步优先, 错误码体系, 命名约定)
- `specs/03-commit.md` — Commit 格式 (`<type>: <描述>`, AI 代码必须标注 `Co-Authored-By`)
- `specs/04-review.md` — PR 流程 (Draft→Review→Approve→Merge, PR < 500 行)

## 常用命令

```bash
# 基础设施
docker compose up -d                          # 启动 PG, Redis, Kafka, MinIO
docker compose --profile phase2 up -d          # 启动 Phase 2 中间件 (Milvus, ES)

# 开发
pytest                                         # 全部测试
pytest services/tts-svc/tests/                 # 单服务测试
ruff check .                                   # Lint
black --check .                                # 格式检查
mypy libs/ services/                           # 类型检查

# Proto
bash scripts/compile_protos.sh                 # 编译所有 .proto → Python stubs

# Docker
docker build -f services/gateway-svc/Dockerfile -t gateway-svc .
```

## 开发阶段

| 阶段 | 状态 | 内容 |
|---|---|---|
| **Phase 1** | ✅ 完成 | 16 微服务骨架, gRPC+Kafka, CI/CD, ~500 测试 (所有 AI 模块为 mock) |
| **Phase 2** | 📋 计划 | AI 集成: CosyVoice2, Wav2Lip, Qwen-3-7B, NLP, RAG, 自托管 LLM |
| **Phase 3** | 📋 计划 | 全人克隆: 3DGS/NeRF 实时渲染, Few-shot 音色克隆, 微表情/动作克隆 |

详见 `docs/Phase2-AI集成实施计划.md`

## AI 辅助规则

1. **所有 AI 生成代码必须在 commit message 中标注 `Co-Authored-By: Claude <noreply@anthropic.com>`**
2. Claude Code 自动创建的 `worktree-*` 分支是临时的，合并后必须删除
3. 永远不要直接 push 到 `main` — 从 `main` 切 feature 分支，PR 合并
4. 合并策略: Squash Merge，一个 PR 压成一个干净 commit
5. 优先使用项目共享库 (`libs/common`, `libs/db`, `libs/kafka`)，不要重复造轮子

## 关键约定

- **Python 3.11+** 后，所有 I/O 操作用 `async/await`
- **错误处理**用 `libs.common.errors.AppError`，不要用裸 `Exception` 或 `HTTPException`
- **日志**用 `structlog`，不用 `print()`
- **配置**继承 `libs.common.config.ServiceConfig`，优先级: 环境变量 > ConfigMap > 代码默认值
- **数据库**所有查询通过 `store_id` 过滤 (多租户隔离)
- **Proto**字段只能加不能删，新字段用 optional/默认值保持向后兼容
