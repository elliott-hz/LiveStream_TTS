# 03 — Commit 规范

## 格式

```
<type>: <简短描述>

<详细说明（可选）>

Co-Authored-By: Claude <noreply@anthropic.com>  # 如果是 AI 辅助生成
```

## Type 前缀

| Type | 用途 | 示例 |
|---|---|---|
| `feat:` | 新功能 | `feat: 新建 llm-svc，接入 Qwen-3-7B 推理` |
| `fix:` | Bug 修复 | `fix: TTS 并发超过 30 路时 OOM` |
| `docs:` | 文档更改 | `docs: Phase 2 AI 集成实施计划` |
| `refactor:` | 重构 | `refactor: 提取 gRPC interceptor 到 libs/common` |
| `chore:` | 杂项 | `chore: 升级 vllm 到 0.7.0` |
| `test:` | 测试 | `test: 补充 interact-svc pipeline 单元测试` |
| `ci:` | CI/CD | `ci: 添加 GPU 节点的 CI 构建` |

## 规则

### 1. 简短描述

- 中文或英文，但全项目统一（本项目用中文描述，英文 type 前缀）
- 不超过 72 个字符
- 动词开头，不加句号
- 说明"做了什么"，不是"做了什么工作"

```
✅ feat: 新建 llm-svc，接入 Qwen-3-7B 推理
❌ feat: llm-svc work
❌ feat: 新建 llm-svc，接入 Qwen-3-7B 推理，包含 vLLM 引擎和 gRPC 接口。
```

### 2. 粒度

一个 commit 只做一件事：

```
✅ 一个好 commit:
feat: llm-svc 新增 GenerateReply gRPC 接口

✅ 另一个好 commit:
feat: llm-svc 新增 vLLM 推理引擎封装

❌ 一个坏 commit (做了太多事):
feat: 新建 llm-svc，新增 tts 缓存，修改 gateway 路由，更新 CI
```

### 3. AI 辅助标注

如果代码是 Claude/AI 辅助生成的，commit message 末尾必须加：

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

这是 **强制要求**，不是可选项。人类 review 过的 AI 代码也要加。

### 4. 中间 commit 可以随意

在 feature 分支上的中间 commit 可以随意写（`wip`、`fix typo` 都行）——因为合并到 `main` 时会 **Squash** 成一个干净 commit。但 PR 的 squash commit message 必须遵守上述规则。

## 示例

### 好的 commit

```bash
git commit -m "feat: llm-svc 新增 vLLM 异步推理引擎

封装 AsyncLLMEngine，支持 INT8 量化加载和流式输出。
配置 max_num_seqs=32，GPU 内存利用率 60%。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

```bash
git commit -m "fix: tts-svc 高频回复缓存未命中时返回空音频

根因：Redis key 前缀拼写错误导致缓存查询全部 miss。
修复：统一 key 前缀为 tts:cache:。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 坏的 commit

```bash
# 太模糊
git commit -m "fix bug"

# 没有 type 前缀
git commit -m "新增功能"

# 做了多件事
git commit -m "feat: 新增 llm-svc，重构 tts-svc，修 gateway bug，更新文档"

# AI 生成但未标注
git commit -m "feat: 新增 render-svc Wav2Lip 口型渲染"
# 缺少: Co-Authored-By: Claude <noreply@anthropic.com>
```
