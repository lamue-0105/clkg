# CLKG 数据上传使用手册

> 版本 v1.0 · 2026-08-26
> 适用于 CLKG 数据采集协作团队

---

## 1. 这是什么

CLKG 数据上传页面是一个**网页工具**，让采集者可以通过浏览器上传填好的 `CLKG_采集模板.xlsx`，系统自动检查数据质量，通过后进入待审核队列，由负责人最终确认入库。

**核心原则**：上传 ≠ 入库。所有数据必须经过负责人人工审核和命令行入库，才能进入知识图谱。

---

## 2. 两种角色

| 角色 | 用途 | 能做什么 |
|---|---|---|
| **采集者 (collector)** | 填表上传数据 | 下载模板、上传 xlsx、查看自己的上传记录和验证报告 |
| **审核者 (reviewer)** | 负责人审核数据 | 采集者的全部权限 + 查看待审核列表、下载原文件、接受/拒绝批次 |

---

## 3. 采集者使用指南

### 3.1 准备工作

1. 向负责人索要：
   - 服务器地址（如 `http://192.168.1.100:8008`）
   - **collector** 用户名和密码
2. 确保电脑和手机在同一局域网内（如连同一个 Wi-Fi）

### 3.2 下载模板

1. 浏览器打开 `http://<服务器地址>:8008/upload.html`
2. 浏览器弹出登录框，输入 collector 用户名密码
3. 点击页面上的 **"↓ 下载当前采集模板"**
4. 用 Excel / WPS / Numbers 打开模板，按 `填写说明` sheet 填数据

### 3.3 填写模板（关键规则）

- **红色必填列**必须填写
- **下拉列**（如 region、entity_type、hasType）必须从下拉选择，不要手敲
- **坐标**：填了经度/纬度就必须填 `CRS_坐标系`
  - 高德地图坐标选 `GCJ-02`
  - GPS 实测坐标选 `WGS84`
  - 不要自己换算坐标系
- **natural_key**：同一对象永远用同一个 key，先查权威清单
- **来源**：每行必须有 `source_name`（Zotero key / 馆藏号 / URL / 田野编号）
- **删除黄色示例行**后再上传

### 3.4 上传数据

1. 打开 `http://<服务器地址>:8008/upload.html`
2. **选择目标区域**：mustang（木斯塘）/ qiaopi（侨批）/ xinjiang（新疆）/ kashgar（喀什）/ liangzhu（良渚）
   - ⚠️ **重要**：一次只能传一个区域。如果表里写了多个区域的数据，系统会拒绝。
3. **选择文件**：点击或拖拽 `.xlsx` 文件到上传区
4. 点击 **"上传并验证"**
5. 等待几秒（验证中）

### 3.5 看懂验证结果

#### ✅ 验证通过

```
批次 ID: upl_20260826_143022_abc123
状态: 待审核
错误 0 / 警告 2
```

- 数据已进入负责人待审核队列
- 等待负责人审核入库即可
- 可以截图保存批次 ID 备查

#### ❌ 验证未通过

系统会列出所有错误，按 sheet 分组：

| 行 | 列 | 级别 | 说明 |
|---|---|---|---|
| 5 | natural_key | error | natural_key 为空 |
| 12 | hasType | error | 值 '寺庙' 不在词表中 |

**常见错误处理**：

| 错误提示 | 怎么办 |
|---|---|
| `natural_key 为空` | 检查该行是否有 key，没有就补一个 |
| `不在词表` | 检查该列是否手敲了错别字，改用下拉选择 |
| `经纬度必须同时填写` | 经度和纬度要么都填，要么都不填 |
| `填写了坐标但未填写 CRS` | 在 `CRS_坐标系` 列选坐标系 |
| `区域不一致` | 检查表里的 region 列是否和页面选择的区域一致 |

改完错误后，**重新上传**（会生成新批次，旧批次不用管）。

### 3.6 查看自己的上传记录

目前页面只显示当前上传结果。历史记录由负责人统一管理，如需查询请联系负责人。

---

## 4. 审核者（负责人）使用指南

### 4.1 登录

浏览器打开 `http://<服务器地址>:8008/upload.html`，输入 **reviewer** 用户名密码。

### 4.2 查看待审核批次

页面下方会显示 **"待审核批次"** 列表：

```
┌────────────────────────────────────────┐
│ 待审核批次 [2]                          │
├────────────────────────────────────────┤
│ test_e2e.xlsx                          │
│ mustang · collector · 2026-08-26 14:30 │
│ 错误 0 / 警告 4                         │
│ [下载] [接受] [拒绝]                    │
└────────────────────────────────────────┘
```

### 4.3 审核操作

#### 接受批次

1. 点击 **"接受"**
2. 文件移动到 `archive/` 目录
3. 终端执行入库：

```bash
cd ~/clkg
python -m ingest.cli template \
  02_data_collection/upload_queue/archive/<batch_id>/<文件名>.xlsx
```

4. 标记已入库：

```bash
python 05_viz/upload_queue.py mark-ingested <batch_id> \
  --ingest-batch <ingest 返回的批次号>
```

#### 拒绝批次

1. 点击 **"拒绝"**
2. 输入拒绝原因（可选）
3. 文件移动到 `rejected/` 目录
4. 通知采集者修改后重新上传

### 4.4 命令行管理（推荐）

除了网页，也可以用 CLI 管理批次：

```bash
# 查看所有批次
python 05_viz/upload_queue.py list

# 只看待审核
python 05_viz/upload_queue.py list --status pending_review

# 接受
python 05_viz/upload_queue.py accept <batch_id> --reviewer 你的名字

# 拒绝
python 05_viz/upload_queue.py reject <batch_id> --reviewer 你的名字 --note "原因"

# 标记入库成功
python 05_viz/upload_queue.py mark-ingested <batch_id> --ingest-batch <批次号>

# 标记入库失败（保留处理记录）
python 05_viz/upload_queue.py mark-failed <batch_id> --note "失败原因"
```

### 4.5 批次状态说明

| 状态 | 含义 | 下一步 |
|---|---|---|
| `received` | 刚上传，待验证 | 系统自动验证 |
| `validating` | 验证中 | 等待 |
| `validation_failed` | 验证未通过 | 采集者修改后重新上传 |
| `pending_review` | 待审核 | 负责人 accept 或 reject |
| `accepted` | 已接受，待入库 | 负责人执行 ingest.cli |
| `rejected` | 已拒绝 | 通知采集者 |
| `ingested` | 已入库 | 完成 |

---

## 5. 服务管理（负责人）

### 5.1 启动服务

```bash
cd ~/clkg

# 设置密码（必须）
export CLKG_COLLECTOR_USER=collector
export CLKG_COLLECTOR_PASSWORD=采集者密码
export CLKG_REVIEWER_USER=reviewer
export CLKG_REVIEWER_PASSWORD=审核者密码

# 可选配置
export CLKG_MAX_UPLOAD_MB=25          # 上传文件大小限制（MB）
export CLKG_UPLOAD_ROOT=/path/to/upload_queue  # 自定义存储路径

# 启动
python 05_viz/run.py
```

### 5.2 确认服务正常

```bash
curl http://127.0.0.1:8008/api/regions
```

返回 JSON 数据即正常。

### 5.3 查看你的局域网 IP

```bash
# macOS
ipconfig getifaddr en0

# 或
ifconfig | grep "inet " | grep -v 127.0.0.1
```

采集者访问地址：`http://<这个IP>:8008/upload.html`

### 5.4 停止服务

终端按 `Ctrl+C`。

### 5.5 数据备份

上传的批次数据存储在：

```
02_data_collection/upload_queue/
├── queue.sqlite3          # 批次数据库
├── incoming/              # 上传临时文件
├── pending/{region}/      # 待审核文件
├── rejected/              # 已拒绝文件
├── archive/               # 已接受/已入库文件
└── reports/               # 验证报告
```

**建议定期备份** `queue.sqlite3` 和整个 `upload_queue/` 目录。

---

## 6. 安全注意事项

1. **密码不要分享给无关人员**
   - collector 密码只给填表的人
   - reviewer 密码只有负责人知道

2. **Basic Auth 不是加密**
   - 密码在局域网内以 Base64 传输，技术上可被截获
   - 不要在公共 Wi-Fi 或不信任的网络中使用
   - 如需更高安全，联系负责人配置 HTTPS

3. **上传文件有大小限制**
   - 默认 25 MB，超限会被拒绝
   - 大文件请联系负责人直接传输

4. **不要上传敏感个人信息**
   - 采集数据涉及人物时，遵守研究伦理
   - 匿名化处理按 SOP 执行

---

## 7. 常见问题

### Q: 上传页面打不开？

1. 确认服务已启动（负责人执行 `python 05_viz/run.py`）
2. 确认 IP 地址正确
3. 确认在同一局域网
4. 尝试用 `http://127.0.0.1:8008/upload.html`（负责人本机测试）

### Q: 登录后页面空白？

- 检查浏览器控制台（F12）是否有错误
- 确认 `clkg-theme.css` 能正常加载
- 尝试强制刷新（Ctrl+Shift+R 或 Cmd+Shift+R）

### Q: 上传后一直"验证中"？

- 大文件验证需要时间，30 秒内属正常
- 超过 1 分钟无响应，联系负责人查看服务器日志

### Q: 验证通过但负责人看不到？

- 确认批次状态是 `pending_review`
- 负责人点击"刷新列表"
- 或 CLI 执行 `python 05_viz/upload_queue.py list --status pending_review`

### Q: 可以手机上传吗？

- 可以，手机浏览器打开同一地址即可
- 但 Excel 填写建议在电脑完成，手机仅用于紧急提交

### Q: 上传错了能撤回吗？

- 验证未通过的批次自动进 `rejected/`，无需处理
- 验证通过但尚未审核的批次，负责人可以 reject
- 已入库的数据不能通过页面撤回，需负责人数据库操作

---

## 8. 联系与支持

- **SOP 详细说明**：`02_data_collection/SOP_数据采集.md`
- **模板问题**：查看模板内的 `填写说明` sheet
- **技术问题**：联系负责人（lamue）
- **GitHub Issues**：https://github.com/lamue-0105/clkg/issues

---

*本手册随系统更新而修订，最新版本见 `02_data_collection/UPLOAD_使用手册.md`。*
