# 开发规范与规则

> 所有开发人员必须遵守。违反规则 = PR 被拒。

## 目录

| 编号 | 文档 | 内容 |
|---|---|---|
| 01 | [Git 分支管理](./01-git-branch.md) | 分支命名、生命周期、合并策略、worktree 清理 |
| 02 | [代码风格](./02-code-style.md) | Python 规范、类型标注、项目结构、错误处理 |
| 03 | [Commit 规范](./03-commit.md) | 提交信息格式、粒度、签名要求 |
| 04 | [Code Review 流程](./04-review.md) | PR 提交、Review 标准、合并条件 |

## 核心原则

1. **main 分支神圣不可侵犯** — 永远可部署，永远不直接 push
2. **小步提交，频繁合并** — 一个 PR 不超过 500 行改动
3. **先读规范再写代码** — 不要问"应该怎么命名"，查文档
4. **机器人不算贡献者** — Claude/Co-pilot 生成代码需标注 `Co-Authored-By: Claude <noreply@anthropic.com>`
