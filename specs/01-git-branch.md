# 01 — Git 分支管理

## 分支模型

本项目采用 **Trunk-Based Development**：`main` 是唯一的长期分支，所有开发通过短生命周期功能分支 + PR 合并。

```
main ──────────────────────────────────────────────────────→
  │                                                          
  ├── feature/qwen-llm-svc ── PR → merge → delete           
  ├── fix/tts-oom-bug ────── PR → merge → delete            
  └── docs/phase2-plan ───── PR → merge → delete            
```

## 分支命名

| 前缀 | 用途 | 示例 |
|---|---|---|
| `feature/` | 新功能开发 | `feature/llm-svc`, `feature/wav2lip-render` |
| `fix/` | Bug 修复 | `fix/gateway-auth-panic`, `fix/tts-memory-leak` |
| `docs/` | 纯文档更改 | `docs/api-reference`, `docs/deploy-guide` |
| `refactor/` | 重构（不改功能） | `refactor/grpc-interceptor`, `refactor/db-session` |
| `chore/` | 杂项（依赖升级、CI 配置） | `chore/update-vllm-0.7`, `chore/ci-cache` |
| `experiment/` | 实验性代码，可能不合入 | `experiment/whisper-stt` |

**命名规则：**
- 全小写，连字符分隔（kebab-case）
- 简短但可读，不超过 50 个字符
- 不要用 `worktree-` 前缀——那是 Claude Code 自动创建的临时分支，禁止手动使用

**错误示范：**
```
❌ worktree-xxx            # 临时分支，会被清理
❌ feature_llm_svc         # 用下划线，不是连字符
❌ fix                    # 不知道修什么
❌ my-branch              # 无意义
❌ feature/数字人直播       # 不要用中文
```

## 分支生命周期

```
创建 → 开发 → PR → Review → 合并 → 删除
```

1. **创建：** 从 `main` 的最新 commit 切出
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/xxx
   ```
2. **开发：** 在分支上提交，保持 commit 干净有意义
3. **PR：** push 到 remote，创建 Draft PR → 开发完成转 Ready
4. **合并：** Review 通过后，Squash Merge 到 `main`
5. **删除：** 合并后立即删除远程和本地分支
   ```bash
   git branch -d feature/xxx
   git push origin --delete feature/xxx
   ```

## main 分支规则

| 规则 | 说明 |
|---|---|
| **禁止直接 push** | 任何人（包括管理员）都不能 `git push origin main` |
| **禁止 force push** | `main` 历史不可改写 |
| **始终可部署** | `main` 上的 HEAD 应该随时可以上生产 |
| **合并前必须 CI 通过** | lint → test → build 全绿才允许 merge |

## worktree 分支（Claude Code 自动管理）

Claude Code 在并行开发时可能自动创建 `worktree-*` 分支。这些分支的特点：

- 命名格式：`worktree-<task-name>`（如 `worktree-competitor-analysis`）
- **临时性质：** 任务完成后应立即删除
- **不要手动使用：** 不要基于 worktree 分支做开发
- **定期清理：**

```bash
# 查看所有 worktree
git worktree list

# 清理所有已完成的 worktree 分支和目录
git branch | grep worktree | xargs -I{} git branch -D {}
rm -rf .claude/worktrees/*
git worktree prune
```

## 合并策略

| 分支类型 | 合并方式 | 说明 |
|---|---|---|
| `feature/*` | **Squash Merge** | 一个 feature 压成 1 个 commit |
| `fix/*` | **Squash Merge** | 一个 bug 压成 1 个 commit |
| `docs/*` | **Squash Merge** | 文档更改压成 1 个 commit |
| `refactor/*` | **Squash Merge** | 重构压成 1 个 commit |
| `chore/*` | **Squash Merge** | 杂项压成 1 个 commit |

**为什么 Squash：** `main` 上只保留"完成了一个什么功能"，不保留开发过程中的 "wip"、"fix typo"、"try again" 等中间 commit。

## 冲突解决

1. 在功能分支上 `git rebase main`（不要 merge main 进 feature）
2. 解决冲突后 `git push --force-with-lease`（只允许在自己的 feature 分支上 force push）
3. 确保 CI 仍然通过

```bash
git checkout feature/xxx
git fetch origin main
git rebase origin/main
# 解决冲突...
git add .
git rebase --continue
git push --force-with-lease origin feature/xxx
```
