# CLKG 数据上传系统开发报告

**日期**：2026-08-26
**阶段**：P0 — 采集上传与质量闸门
**对应计划**：`Documents/博士研究进度/CLKG_上传页面完整实施计划.md`

---

## 一、我做了什么

在现有 `05_viz/` FastAPI 演示服务基础上，建成了一套**带密码保护、自动验证、批次追踪**的数据采集上传系统。采集者通过浏览器上传 Excel，系统自动运行 `preingest_validator`，通过者进入待审核队列，负责人审核后人工入库。

**核心目标达成**：把每次提交变成**可追溯、可审核、可恢复**的研究批次，而不是简单的文件传递。

---

## 二、新建和修改了哪些文件

### 新建（8 个文件）

| 文件 | 干什么用 |
|---|---|
| `05_viz/public/upload.html` | 上传页面。单栏 720px，复用 explorer 暖白风格。含上传表单、验证结果展示、reviewer 待审核列表 |
| `05_viz/public/clkg-theme.css` | 共享样式。从 explorer.html 提取全部 CSS 变量和组件样式，新增 upload 页面专用样式 |
| `05_viz/public/explorer.html` | 迁移自原文件。改用外部 CSS，导航加"数据上传"，API 地址改 `location.origin` |
| `05_viz/public/workbench.html` | 迁移。导航加"数据上传"，API 地址改 `location.origin` |
| `05_viz/public/topics.html` | 迁移。导航加"数据上传"，API 地址改 `location.origin` |
| `05_viz/upload_service.py` | 上传包装层。文件安全（大小/扩展名/SHA-256/路径穿越）、模板预检（sheet 识别 + region 一致性）、调用 `preingest_validator`、批次文件生命周期管理 |
| `05_viz/upload_queue.py` | SQLite 批次队列。`upload_batch` + `upload_event` 两表，完整状态机，CLI 管理工具 |
| `02_data_collection/upload_queue/` | 批次存储目录。`incoming/`（临时）、`pending/{region}/`（待审核）、`rejected/`（已拒绝）、`archive/`（已接受/已入库）、`reports/`（验证报告） |

### 修改（3 个文件）

| 文件 | 改了什么 |
|---|---|
| `05_viz/api.py` | 加 HTTP Basic Auth（collector/reviewer 双角色）、9 个上传相关端点、静态文件 catch-all 路由、移除宽松 CORS |
| `05_viz/run.py` | 绑定 `0.0.0.0:8008`（局域网开放）、环境变量缺失警告 |
| `requirements.txt` | 加 `fastapi`、`uvicorn`、`python-multipart` |

---

## 三、设计上做了哪些关键决定

### 1. 不直接挂载 `05_viz/`，建立 `public/` 目录

**为什么**：原方案 `app.mount("/", StaticFiles(directory="05_viz"))` 会暴露 `api.py`、`rules.py`、`upload_queue.py` 等开发文件。测试确认 `/api.py` 返回 200。

**做法**：新建 `05_viz/public/`，只放 HTML 和 CSS。API 路由优先匹配，未匹配的走 catch-all 路由 serve `public/`。测试确认 `/api.py` 等全部 404。

### 2. 双角色 HTTP Basic Auth

**为什么**：采集者和负责人权限不同。collector 只能上传和看自己的批次；reviewer 能看待审核列表、下载原文件、审核。

**做法**：FastAPI `HTTPBasic` + `secrets.compare_digest`。`Principal` 类携带 `username` 和 `role`。环境变量必须设置，缺失时服务拒绝启动。

### 3. SQLite 批次队列，而不是扫描文件夹

**为什么**：文件夹扫描无法表达状态机（`received → validating → pending_review → accepted/rejected → ingested`），也无法记录事件日志。

**做法**：`queue.sqlite3` 两表。`upload_batch` 存批次元数据（状态、区域、上传者、文件信息、验证结果、审核人、入库批次号）。`upload_event` 存每次状态变更的审计日志。

### 4. 上传 ≠ 入库，保留人工审核

**为什么**：自动入库绕过质量闸门，违背 SOP 原则。

**做法**：验证通过只进 `pending_review`，负责人必须显式 `accept`，然后手动执行 `ingest.cli`，最后 `mark-ingested` 回写状态。入库失败可 `mark-failed` 保留记录。

### 5. 区域一致性预检

**为什么**：一次上传一个区域是 P0 规则。混合区域工作簿会导致数据路由错误。

**做法**：`precheck_template()` 在 `validate_workbook()` 之前运行，扫描所有有效数据行的 `region` 列，与页面选择比对。不一致直接拒绝。

### 6. 报告路径脱敏

**为什么**：验证报告含服务器临时文件绝对路径，不能返回给前端。

**做法**：`run_validation()` 生成报告后，把报告内容中的临时路径替换为 `batch_id`。API 响应只返回 `report_url`，不返回服务器路径。

---

## 四、技术实现要点

### 动态导入的 `@dataclass` 兼容性问题

**现象**：`upload_service.py` 和 `api.py` 被 `run.py` 用 `importlib.util.spec_from_file_location` 动态导入时，`@dataclass` 报 `AttributeError: 'NoneType' object has no attribute '__dict__'`。

**原因**：Python `dataclasses` 处理类型注解时，会通过 `cls.__module__` 查找 `sys.modules`，但动态导入的模块尚未注册。

**修复**：`UploadConfig` 和 `Principal` 从 `@dataclass` 改为普通类，显式写 `__init__`。

### FastAPI 路由顺序

**现象**：`/api/upload/pending` 被 `/api/upload/{batch_id}` 捕获，返回"批次不存在"。

**修复**：把 `/api/upload/pending` 移到 `/api/upload/{batch_id}` 之前定义。

### 文件命名一致性

**现象**：上传时 `move_to_pending` 用 `xlsx_path.name`（含 `batch_id_` 前缀），审核时用 `original_filename`（不含前缀），导致 `FileNotFoundError`。

**修复**：`move_to_pending/rejected/archive` 加 `_strip_batch_prefix()`，统一恢复原始文件名存储。

### `preingest_validator` 未导入

**现象**：`api.py` 引用 `preingest_validator.__version__`，但该模块只在 `upload_service.py` 中导入，`api.py` 命名空间不存在。

**修复**：改为 `upload_service.preingest_validator.__version__`。

---

## 五、测试清单与结果

### 认证与权限

| 测试 | 预期 | 结果 |
|---|---|---|
| 未登录访问 upload.html | 401 | ✅ |
| 错误密码 | 401 | ✅ |
| collector 访问 `/api/upload/pending` | 403 | ✅ |
| reviewer 访问 `/api/upload/pending` | 200 | ✅ |
| collector 上传 | 200 | ✅ |
| reviewer 审核（accept/reject） | 200 | ✅ |

### 文件安全

| 测试 | 预期 | 结果 |
|---|---|---|
| `.txt` 文件 | 400 拒绝 | ✅ |
| `.xls` / `.xlsm` | 400 拒绝 | ✅ |
| 30MB 超限文件 | 400 拒绝 | ✅ |
| 空文件 | 400 拒绝 | ✅ |
| 路径穿越文件名 | 清理后拒绝 | ✅ |
| 伪装 `.xlsx`（非 ZIP 头） | 400 拒绝 | ✅ |

### 模板与区域

| 测试 | 预期 | 结果 |
|---|---|---|
| 零识别 sheet | 400 拒绝 | ✅ |
| 混合区域工作簿 | 预检拦截或示例行跳过 | ✅（示例行正确跳过） |
| 页面选 mustang，表内写 qiaopi | 400 区域不一致 | ✅ |
| 无效区域 | 400 拒绝 | ✅ |

### 暴露面

| 测试 | 预期 | 结果 |
|---|---|---|
| `/api.py` | 404 | ✅ |
| `/rules.py` | 404 | ✅ |
| `/upload_queue.py` | 404 | ✅ |
| `/upload_service.py` | 404 | ✅ |
| `/catalog.py` | 404 | ✅ |
| `/run.py` | 404 | ✅ |

### 完整业务流程

| 步骤 | 结果 |
|---|---|
| 上传 → 验证通过 → `pending_review` | ✅ |
| 查看待审核列表 | ✅ |
| 下载验证报告（JSON + Markdown） | ✅ |
| reviewer accept → `accepted` → `archive/` | ✅ |
| CLI `mark-ingested` → `ingested` | ✅ |
| reviewer reject → `rejected` | ✅ |
| 下载原文件（各状态） | ✅ |
| CLI `list` 各状态筛选 | ✅ |

---

## 六、当前系统边界（P0 明确不做的事）

- **不做用户注册**：单一 collector + reviewer 密码，无多用户系统
- **不做文件版本管理**：上传即覆盖，不保留历史版本
- **不做在线编辑**：只上传，不改 Excel
- **不做自动入库**：所有批次必须人工 `ingest.cli`
- **不做 HTTPS**：Basic Auth 在 HTTP 下明文传输，信任局域网环境
- **M4 natural_key 冲突为占位值**：界面已标注，不作为最终确认

---

## 七、使用方式

### 启动

```bash
cd ~/clkg
export CLKG_COLLECTOR_USER=collector
export CLKG_COLLECTOR_PASSWORD=xxx
export CLKG_REVIEWER_USER=reviewer
export CLKG_REVIEWER_PASSWORD=yyy
python 05_viz/run.py
```

### 采集者

浏览器打开 `http://<IP>:8008/upload.html`，collector 登录，下载模板、填表、上传、看验证结果。

### 负责人

```bash
# 网页：upload.html 底部看待审核列表，点 accept/reject
# CLI：
python 05_viz/upload_queue.py list --status pending_review
python 05_viz/upload_queue.py accept <batch_id> --reviewer 名字
python -m ingest.cli template <文件路径>
python 05_viz/upload_queue.py mark-ingested <batch_id> --ingest-batch <批次号>
```

---

## 八、后续路线（P1+）

| 优先级 | 事项 |
|---|---|
| P1 | HTTPS 反向代理（Caddy/Nginx + 自签名证书） |
| P1 | 采集者历史批次查询页面 |
| P2 | 自动 ingest（审核通过后自动执行，无需人工 CLI） |
| P2 | 邮件/微信通知（新上传、审核结果） |
| P3 | 多用户系统（每人独立账号） |
| P3 | 大文件分片上传 |

---

## 九、文件清单（最终状态）

```
05_viz/
├── api.py                    # 修改：认证 + 上传端点 + 静态文件
├── run.py                    # 修改：0.0.0.0 + 环境变量检查
├── upload_service.py         # 新建：上传包装层
├── upload_queue.py           # 新建：SQLite 队列 + CLI
├── catalog.py                # 未动
├── rules.py                  # 未动
├── demo_queries.sql          # 未动
├── explorer.html             # 原文件（已迁移到 public/）
├── workbench.html            # 原文件（已迁移到 public/）
├── topics.html               # 原文件（已迁移到 public/）
└── public/                   # 新建：唯一可公开访问目录
    ├── clkg-theme.css        # 共享样式
    ├── explorer.html         # 迁移 + 导航更新
    ├── workbench.html        # 迁移 + 导航更新
    ├── topics.html           # 迁移 + 导航更新
    └── upload.html           # 新建：上传页面

02_data_collection/
├── upload_queue/             # 新建：批次存储
│   ├── queue.sqlite3
│   ├── incoming/
│   ├── pending/{region}/
│   ├── rejected/
│   ├── archive/
│   └── reports/
└── UPLOAD_使用手册.md        # 新建：采集者+负责人手册

requirements.txt              # 修改：加 fastapi/uvicorn/python-multipart
```

---

*本报告由开发过程实际代码和测试记录整理而成。*
