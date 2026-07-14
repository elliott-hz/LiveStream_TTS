# 02 — 代码风格

## 语言与工具链

| 工具 | 用途 | 配置文件 |
|---|---|---|
| **Python 3.11** | 所有服务的最低版本 | `pyproject.toml` |
| **Ruff** | Linting + 部分格式化 | `pyproject.toml [tool.ruff]` |
| **Black** | 代码格式化 | `pyproject.toml [tool.black]` |
| **MyPy** | 静态类型检查 | `pyproject.toml [tool.mypy]` |
| **Pytest** | 测试框架 | `pyproject.toml [tool.pytest.ini_options]` |

**提交前必须通过：**
```bash
ruff check .          # 无错误
black --check .       # 格式正确
mypy libs/ services/  # 类型正确（渐进式，至少不改出新的 type error）
pytest                # 全部测试通过
```

## Python 规范

### 类型标注

所有公共函数必须有类型标注：

```python
# ✅ 正确
def get_user(user_id: str, store_id: str) -> User | None:
    ...

async def list_products(
    store_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Product], int]:
    ...

# ❌ 错误
def get_user(user_id, store_id):    # 无类型
    ...

async def list_products(store_id, **kwargs):  # 无类型
    ...
```

### 异步优先

所有 I/O 操作使用 async/await：

```python
# ✅ 正确
async def get_user(user_id: str) -> User:
    async with db.session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

# ❌ 错误
def get_user(user_id: str) -> User:  # 同步
    with db.session() as session:
        ...
```

### 错误处理

使用项目统一的错误码体系（`libs/common/errors.py`）：

```python
from libs.common.errors import AppError, ErrorCode, Domain

# ✅ 正确：使用项目错误体系
raise AppError(
    code=ErrorCode.USER_NOT_FOUND,
    domain=Domain.USER,
    message=f"User {user_id} not found",
)

# ❌ 错误：裸 Exception 或 HTTPException
raise Exception("user not found")
raise HTTPException(status_code=404, detail="not found")
```

### 日志

使用 structlog 结构化日志：

```python
import structlog
logger = structlog.get_logger(__name__)

# ✅ 正确：结构化日志
logger.info("user_login", user_id=user_id, store_id=store_id, ip=request_ip)

# ❌ 错误：print 或 f-string 日志
print(f"User {user_id} logged in from {request_ip}")
logger.info(f"User {user_id} logged in")  # 不要用 f-string
```

## 项目结构

每个微服务遵循标准目录结构：

```
services/{name}-svc/
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── k8s/
│   ├── configmap.yaml
│   ├── deployment.yaml
│   └── service.yaml
├── src/
│   ├── __init__.py
│   ├── main.py           # 入口：FastAPI + gRPC Server
│   ├── config.py         # 配置类（继承 ServiceConfig）
│   ├── api/
│   │   └── grpc_impl.py  # gRPC servicer 实现
│   ├── http/
│   │   └── routes.py     # HTTP/REST 路由
│   ├── models/
│   │   └── *.py          # SQLAlchemy ORM 模型
│   └── services/
│       └── *.py          # 业务逻辑
└── tests/
    ├── conftest.py
    └── test_*.py
```

## 配置管理

继承 `libs.common.config.ServiceConfig`，使用 3 层优先级：

```
环境变量 > K8s ConfigMap > 代码默认值
```

```python
from libs.common.config import ServiceConfig

class MyConfig(ServiceConfig):
    def __init__(self):
        super().__init__("my-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int("GRPC_PORT", 50050)
```

## 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 文件名 | 蛇形命名 (snake_case) | `live_room_service.py` |
| 类名 | 大驼峰 (PascalCase) | `LiveRoomService` |
| 函数/方法 | 蛇形命名 (snake_case) | `get_live_room()` |
| 变量 | 蛇形命名 (snake_case) | `live_room_id` |
| 常量 | 全大写蛇形 | `MAX_CONCURRENT_STREAMS` |
| 私有函数 | 下划线前缀 | `_validate_state()` |
| gRPC 方法 | 大驼峰 | `CreateLiveRoom`, `GetUser` |
| Proto 消息 | 大驼峰 | `CreateLiveRoomRequest` |
| Kafka Topic | 小写点分隔 | `danmaku.raw`, `live.events` |
| 数据库表 | 蛇形命名，复数 | `live_rooms`, `products` |
| 数据库列 | 蛇形命名，单数 | `store_id`, `created_at` |

## 禁止事项

| 禁止 | 原因 |
|---|---|
| `print()` | 用 structlog |
| `except Exception: pass` | 吞掉所有异常 |
| `import *` | 污染命名空间 |
| 硬编码密钥/密码 | 用环境变量或 ConfigMap |
| 同步 I/O 在 async 函数中 | 用 async 版本的库 |
| 超过 200 行的函数 | 拆分 |
| 超过 500 行的文件 | 拆分模块 |
| 注释写中文（可以用，但不鼓励在代码注释中） | docstring 和注释用英文，文档用中文 |
| 裸 `# TODO` | 写成 `# TODO(username): what to do` |
