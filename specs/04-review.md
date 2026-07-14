# 04 — Code Review 流程

## PR 生命周期

```
Draft PR → Ready for Review → Review → Request Changes → Fix → Re-Review → Approve → Merge
```

## 提交 PR

### 1. 先创建 Draft PR

```bash
# push 分支
git push origin feature/xxx

# 创建 Draft PR
gh pr create --draft \
  --title "feat: llm-svc 新增 Qwen-3-7B 推理服务" \
  --body "## 改动内容
- 新建 llm-svc 微服务
- vLLM AsyncLLMEngine 封装
- GenerateReply / StreamReply gRPC 接口

## 测试
- [x] 单元测试通过
- [x] 5 路并发压测通过
- [x] DeepSeek API 降级验证

## 关联
- Phase 2 步骤 1
- Closes #xxx

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

### 2. 开发完成后转 Ready

当以下条件全部满足时，把 Draft 转 Ready：

- [ ] 所有代码改动完成
- [ ] `ruff check` 无错误
- [ ] `black --check` 通过
- [ ] `mypy` 无新增 type error
- [ ] `pytest` 全部通过
- [ ] 自己 review 过一遍 diff
- [ ] PR 描述写清楚改了什么、为什么改、怎么测的

### 3. PR 大小限制

| 改动行数 | 评估 |
|---|---|
| < 200 行 | ✅ 理想，review 很快 |
| 200-500 行 | ⚠️ 可接受，但考虑拆分 |
| > 500 行 | ❌ 必须拆分 |

**拆分技巧：** 如果 PR 超过 500 行，拆成多个小 PR，用 `Depends on #PR编号` 标明依赖关系。

## Review 标准

### Reviewer 必须检查

| 维度 | 检查内容 |
|---|---|
| **正确性** | 逻辑对吗？边界条件处理了吗？空值/并发/超时？ |
| **安全** | 有注入风险吗？敏感数据打印了吗？权限检查到位吗？ |
| **性能** | 有没有 N+1 查询？大循环里调数据库了吗？ |
| **可维护性** | 命名清晰吗？函数太长吗？有重复代码吗？ |
| **错误处理** | 异常兜住了吗？错误信息够定位问题吗？ |
| **测试** | 覆盖核心路径了吗？有边界测试吗？ |

### Review 意见标签

| 标签 | 含义 |
|---|---|
| `[blocking]` | 必须修，不修不能合并 |
| `[nit]` | 小问题，修不修都行 |
| `[question]` | 疑问，需要作者解释 |
| `[praise]` | 写得好，值得表扬 |
| `[suggestion]` | 建议，非强制 |

### Review 时间要求

- 工作日：PR 提交后 **4 小时内** 开始 review
- 紧急修复：通知 reviewer，**1 小时内** review
- 如果 reviewer 忙，明确回复 "明天看" 而不是已读不回

## 合并条件

所有条件满足才能点 Merge：

- [ ] 至少 **1 个 Approve**（核心服务至少 2 个）
- [ ] 所有 CI 检查通过（lint / test / build）
- [ ] 所有 `[blocking]` 评论已解决
- [ ] 分支与 `main` 无冲突（已 rebase）
- [ ] PR 描述完整

## 合并后

```bash
# 1. 切回 main 并拉取最新
git checkout main
git pull origin main

# 2. 删除本地功能分支
git branch -d feature/xxx

# 3. 删除远程功能分支
git push origin --delete feature/xxx
```
