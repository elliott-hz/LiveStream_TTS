# 04 — 代码审查

## 当前模式：Solo 开发

本项目当前为单人开发，**无需 PR、无需 Review**。工作流程：

```
切分支 → 开发 → 自检 → 合并到 main → 删分支
```

## 合并前自检清单

合并到 main 之前，必须确认以下全部通过：

- [ ] `ruff check .` 无错误
- [ ] `black --check .` 通过
- [ ] `mypy libs/ services/` 无新增 type error（渐进式）
- [ ] `pytest` 全部通过
- [ ] 自己看过一遍 `git diff main...feature/xxx`
- [ ] Commit message 符合 [03-commit](./03-commit.md) 规范
- [ ] AI 生成代码标注了 `Co-Authored-By: Claude <noreply@anthropic.com>`

## 什么时候需要 Review

出现以下情况时，合并前应该让 Claude 帮忙检查：

| 场景 | 操作 |
|---|---|
| 改动超过 500 行 | `git diff main | claude "review 这个改动"` |
| 涉及多个服务 | 让 Claude 逐服务确认没有遗漏 |
| 修改了 Proto 定义 | 确认向后兼容 |
| 修改了数据模型 | 确认 migration 不会丢数据 |
| 第一次写某种类型的代码 | 让 Claude 检查是否符合项目规范 |

**实操：**
```bash
# 合并前让 Claude 看一下
git diff main...feature/xxx | claude "review 这个 diff，重点关注正确性和安全性"
```

## 未来：团队模式

当项目有 ≥2 个开发者时，启用以下规则：

1. 所有改动走 PR
2. 至少 1 个 Approve 才能合并
3. PR < 500 行，超过拆分
4. 工作日 4 小时内 review

详细流程见 [04-review-team.md](./04-review-team.md)（届时创建）。
