# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

数字人直播带货 SaaS 平台 — 16 个 Python 3.11 微服务，gRPC + Kafka 通信，PostgreSQL + Redis + MinIO。

## 常用命令

```bash
# 基础设施
docker compose up -d                          # PG, Redis, Kafka
docker compose --profile phase2 up -d          # + Milvus, MinIO (Phase 2)

# 测试
pytest                                          # 全部测试 (~500)
pytest services/tts-svc/tests/                  # 单个服务
pytest services/tts-svc/tests/test_http_server.py  # 单个文件
pytest -m unit                                  # 仅单元测试
pytest -m "not slow"                            # 跳过慢测试
pytest -m "not integration"                     # 跳过集成测试

# 代码质量
ruff check .                                    # Lint
black --check .                                 # 格式检查
black .                                         # 自动格式化
mypy libs/ services/                            # 类型检查

# Proto
bash scripts/compile_protos.sh                  # 编译所有 .proto → Python stubs

# Docker
docker build -f services/gateway-svc/Dockerfile -t gateway-svc .
```

## 架构核心

### 通信模式
| 通道 | 用途 |
|---|---|
| **FastAPI HTTP** | 外部 REST API，通过 `gateway-svc` 统一暴露 |
| **gRPC** | 服务间同步调用，19 个 proto 定义在 `libs/proto/` |
| **Kafka** | 异步事件流，9 个 topic 定义在 `libs/kafka/__init__.py:Topics` |
| **WebSocket** | TTS 流式音频输出 |

### 实时互动管线（核心运行时路径）
```
弹幕 → interact-svc → nlp-svc (意图/情感/敏感词)
                    → knowledge-svc (RAG 检索)
                    → llm-svc (生成回复) / DeepSeek API (降级)
                    → tts-svc (语音合成) → render-svc (口型渲染) → stream-svc (RTMP 推流)
```

### 多租户隔离
- 租户 = `Store`（店铺），所有核心实体带 `store_id`
- JWT 包含 `store_id`，gateway 代理自动注入 gRPC metadata
- 数据库查询必须通过 `store_id` 过滤
- RBAC: `merchant_admin / editor / viewer`（租户级）+ `super_admin`（平台级）

### 配置优先级
```
环境变量 > K8s ConfigMap > 代码默认值
```
所有配置类继承 `libs.common.config.ServiceConfig`。

### 错误码体系（`libs/common/errors.py`）
| 范围 | 类别 |
|---|---|
| 1xxx | Auth (UNAUTHENTICATED, PERMISSION_DENIED, TOKEN_EXPIRED) |
| 2xxx | Validation (INVALID_ARGUMENT, MISSING_REQUIRED_FIELD) |
| 3xxx | Not Found (USER_NOT_FOUND, PRODUCT_NOT_FOUND, ...) |
| 4xxx | Business Logic (QUOTA_EXCEEDED, INSUFFICIENT_BALANCE, ...) |
| 5xxx | Internal (INTERNAL_ERROR, DATABASE_ERROR, CACHE_ERROR) |
| 6xxx | External (LLM_API_ERROR, TTS_SYNTHESIS_FAILED, ...) |

使用方式：`raise AppError(code=ErrorCode.USER_NOT_FOUND, domain=Domain.USER, message="...")`
快捷函数：`not_found()`, `invalid_arg()`, `internal()`

## 项目结构

```
services/{name}-svc/       # 16 个微服务，命名统一 -svc 后缀
├── src/
│   ├── main.py            # FastAPI + gRPC 双入口
│   ├── config.py          # 继承 ServiceConfig
│   ├── api/grpc_impl.py   # gRPC servicer 实现
│   ├── http/routes.py     # REST 路由
│   ├── models/            # SQLAlchemy ORM
│   └── services/          # 业务逻辑
├── tests/                 # conftest.py + test_*.py
├── k8s/                   # configmap, deployment, service
├── Dockerfile
└── requirements.txt

libs/                      # 5 个共享库
├── common/                # ServiceConfig, AppError/ErrorCode, gRPC 工具, structlog
├── db/                    # SQLAlchemy async session 工厂
├── kafka/                 # aiokafka producer/consumer + Topics 常量
├── proto/                 # 19 个 protobuf 定义 + 生成桩代码
└── testing/               # 共享测试 fixtures (async_db) + 假数据 (fake_product/script/user)
```

## 开发规范

所有规范在 `specs/` 目录，摘要如下：

- **分支**: Trunk-Based，Solo 模式无需 PR。从 `main` 切 `feature/` / `fix/` / `docs/` 分支，自检通过后 `--no-ff` merge 回 main，立即删分支
- **合并前自检**: `ruff check . && black --check . && pytest` 全绿
- **Commit**: `<type>: <中文描述>`，AI 生成代码必须标注 `Co-Authored-By: Claude <noreply@anthropic.com>`
- **代码风格**: Python 3.11+, async/await 所有 I/O, structlog 不用 print(), AppError 不用裸 Exception, 类型标注所有公共函数

## 开发阶段

| 阶段 | 状态 | 说明 |
|---|---|---|
| **Phase 1** | ✅ | 16 微服务骨架，gRPC+Kafka，CI/CD，~500 测试。**所有 AI 模块为 mock** |
| **Phase 2** | 📋 进行中 | AI 集成（全云化）：阿里云 TTS API, DeepSeek API, 2D Viseme 口型, NLP CPU 模型, RAG |
| **Phase 3** | 📋 计划 | 全人克隆：3DGS/NeRF 实时渲染，Few-shot 音色克隆，微表情/动作克隆 |

详见 `docs/Phase2-AI集成实施计划.md`

## Kafka Topics

| Topic | 用途 |
|---|---|
| `danmaku.raw` | 平台弹幕原始消息 |
| `danmaku.processed` | NLP 处理后的弹幕 |
| `interaction.reply` | 互动回复 |
| `live.events` | 直播生命周期事件 |
| `audit.events` | 审核事件 |
| `analytics.events` | 数据分析事件 |
| `platform.sync` | 多平台同步任务 |
| `notification.send` | 通知发送 |
| `billing.usage` | 用量计量 |

## Proto 修改注意

- **字段只能加不能删**，新字段用 optional/默认值
- 修改 `.proto` 后运行 `bash scripts/compile_protos.sh` 重新生成桩代码
- 编译依赖：`pip install grpcio-tools mypy-protobuf`
