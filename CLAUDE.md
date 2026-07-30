# CLAUDE.md

## 项目概述

轻量级 AI 直播工具 SaaS — 预录商品视频循环推流 + AI 弹幕互动。单一商户端，无独立管理后台。

- **技术栈：** Python 3.12 + FastAPI + PostgreSQL + Redis + Celery + FFmpeg
- **架构：** 模块化单体（非微服务），PoC 阶段全部 API，规模化后切 GPU
- **文档：** `docs/` 目录，入口 `docs/README.md`

## 文档导航

| 文档 | 用途 |
|------|------|
| `docs/产品需求文档-PRD.md` | 完整功能规格 |
| `docs/技术实施方案.md` | 技术栈、目录结构、DB模型、API设计、实施路线 |
| `docs/技术调研报告.md` | 平台接入、智能回复、视频解析、数据同步 |
| `docs/系统架构方案.md` | 服务职责、数据流、规模测算、部署拓扑 |
| `docs/成本精算方案.md` | 全API vs GPU 成本对比 |
| `docs/团队配置与执行计划.md` | 10人团队、4个月Roadmap |

## 常用命令

```bash
# 开发环境
docker compose up -d                    # PG + Redis + MinIO + Milvus
cd backend && uvicorn main:app --reload # FastAPI 热重载
cd backend && celery -A workers worker  # Celery Worker

# 代码质量
ruff check .                            # Lint
black --check .                         # 格式检查
pytest                                  # 测试
```

## 核心设计原则

- **模块化单体**：按功能模块分目录（`backend/modules/`），模块间通过共享服务层调用，不通过 RPC
- **多租户**：所有业务表带 `merchant_id`，JWT 包含 store_id，中间件自动注入
- **异步优先**：所有 I/O 操作 async/await（FastAPI + SQLAlchemy async）
- **配置优先级**：环境变量 > 配置文件 > 代码默认值
- **AI 全部 API 起步**：LLM（DeepSeek）、TTS（CosyVoice）、ASR（阿里云）、场景检测（阿里云智能媒体）。规模化后切本地 GPU
- **平台适配器**：每个直播平台一个 Adapter，实现能力协商（推流/弹幕/弹品/回复），上层根据能力矩阵做降级
