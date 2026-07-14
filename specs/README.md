# 开发规范与规则

> 所有开发人员必须遵守。Solo 开发，直接 merge，无需 PR。

## 目录

| 编号 | 文档 | 内容 |
|---|---|---|
| 01 | [Git 分支管理](./01-git-branch.md) | 分支命名、生命周期、合并策略、worktree 清理 |
| 02 | [代码风格](./02-code-style.md) | Python 规范、类型标注、项目结构、错误处理 |
| 03 | [Commit 规范](./03-commit.md) | 提交信息格式、粒度、签名要求 |
| 04 | [代码审查](./04-review.md) | Solo 模式 (当前) vs 团队模式 (未来) |

## 核心原则

1. **main 分支可部署** — 合并前确保 lint + test 通过
2. **小步提交，频繁合并** — 一个任务完成后立即合入 main
3. **先读规范再写代码** — 不要问"应该怎么命名"，查文档
4. **机器人不算贡献者** — Claude/Co-pilot 生成代码需标注 `Co-Authored-By: Claude <noreply@anthropic.com>`
5. **Solo 模式** — 无需 PR 和 Review，切分支开发 → 自检通过 → 直接合并到 main → 删分支
