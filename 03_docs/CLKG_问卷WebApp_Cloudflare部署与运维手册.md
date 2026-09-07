---
title: CLKG 问卷 Web App：Cloudflare 部署与运维手册
status: 准备部署
created: 2026-09-07
tags:
  - CLKG
  - 问卷
  - Cloudflare
  - 运维
  - 数据备份
---

# CLKG 问卷 Web App：Cloudflare 部署与运维手册

> [!abstract] 用途
> 本手册用于将“文化遗产跨类型数据组织与研究需求调查”作为 CLKG 网站的长期模块运行。首个问卷上线后，后续问卷遵循同一部署、数据管理与备份流程。

## 1. 目标与边界

### 1.1 长期访问地址

- CLKG 主站：`shapc-lab.cn`（后续建设）
- 问卷应用：`survey-clkg.shapc-lab.cn`
- 管理后台：`survey-clkg.shapc-lab.cn/admin`

问卷应用不再依赖问卷星、腾讯文档或 `chatgpt.site`。它是 CLKG 的独立 Web App，后续可扩展为“调查问卷目录”，保留历史问卷及题目版本。

### 1.2 数据职责分离

| 系统 | 保存内容 | 不保存内容 |
| --- | --- | --- |
| CLKG PostgreSQL + PostGIS | 遗产对象、GIS、证据、实体关系、研究数据 | 调研答卷 |
| Cloudflare D1 | 匿名问卷答卷、题目版本、提交时间 | 遗产原始数据、数据库账号密码 |
| Cloudflare R2 | 加密后的每日答卷备份 | 公开可访问的答卷文件 |

> [!warning] 基本原则
> 匿名不等于可以公开。答卷、导出 CSV、备份文件均不可提交到公开 GitHub 仓库，也不可配置为公开对象存储。

## 2. 应用架构

```text
研究者（微信 / 浏览器）
        ↓ HTTPS
survey-clkg.shapc-lab.cn
        ↓
Cloudflare Worker（问卷页面、提交接口、管理员后台）
        ├─ D1：实时保存匿名答卷
        └─ 每日 Cron：AES-256-GCM 加密 → R2 私有备份桶
                                           ↓
                                   仅管理员可下载并恢复
```

### 2.1 前端与后端职责

- 前端：展示研究说明、题目与选项；收集选择；显示提交结果。
- 后端：校验必答项、拒绝异常请求、写入 D1、验证管理员会话、生成 CSV。
- 管理后台：仅供研究者本人登录，查看、检索和导出答卷。
- 自动备份：每天 02:15（中国标准时间，UTC 前一日 18:15）生成一份完整的加密快照，存入私有 R2。

## 3. 上线前准备清单

- [ ] 注册 Cloudflare 账号并完成邮箱验证。
- [ ] 在 Cloudflare 添加域名 `shapc-lab.cn`。
- [ ] 在阿里云域名控制台修改为 Cloudflare 提供的两条名称服务器；修改前先记录现有 DNS 记录。
- [ ] 在 Cloudflare 创建 D1 数据库：`clkg-survey`。
- [ ] 在 Cloudflare 创建私有 R2 存储桶：`clkg-survey-backups`；不要开启 `r2.dev` 公共访问或自定义公共域名。
- [ ] 生成并保存三个新密钥：`ADMIN_PASSWORD`、`ADMIN_SESSION_SECRET`、`BACKUP_ENCRYPTION_KEY`。
- [ ] 将三项密钥只写入 Cloudflare Workers 的 Secrets；不得写入仓库、Obsidian、截图或微信群。
- [ ] 在问卷首页保留匿名、用途、数据处理与退出说明。

> [!danger] 密钥规则
> 以前用于测试的管理员密码视为已失效。正式环境必须重新生成；密码管理器是唯一建议的保存位置。

## 4. Cloudflare 部署流程

### 4.1 首次建立资源

在 Cloudflare Dashboard 的 **Workers & Pages** 中完成：

1. 创建 D1 数据库 `clkg-survey`，复制其 database ID。
2. 创建 R2 Bucket `clkg-survey-backups`，保持私有。
3. 在项目中将 `wrangler.jsonc.example` 复制为 `wrangler.jsonc`，填入 D1 database ID。该文件被 Git 忽略。
4. 运行 D1 migration，建立 `survey_responses` 表。
5. 设置三个 Secrets：
   - `ADMIN_PASSWORD`：后台访问密码；
   - `ADMIN_SESSION_SECRET`：随机会话签名密钥；
   - `BACKUP_ENCRYPTION_KEY`：32 字节 base64url AES 密钥。
6. 部署 Worker；部署成功后先使用 Cloudflare 分配的测试地址检查问卷提交和 `/admin` 登录。

### 4.2 绑定正式域名

在 Worker 的 Custom Domain 中添加：

```text
survey-clkg.shapc-lab.cn
```

Cloudflare 会创建证书和路由。`survey` 子域名只用于问卷应用；不要将 D1 或 R2 直接暴露到公网。

### 4.3 发布检查

- [ ] 首页加载正常，封面图可见。
- [ ] 必答项缺失时不能提交。
- [ ] 提交一份测试答卷，后台可以看到。
- [ ] CSV 导出为 UTF-8 with BOM，Excel 中文正常。
- [ ] 未登录访问 `/admin` 会被要求输入密码。
- [ ] 浏览器地址栏显示 HTTPS 锁标志。
- [ ] 旧测试答卷在正式发放前删除或标记为测试。

## 5. 微信真机测试

> [!important] 不通过测试，不正式分发
> Cloudflare 自定义域名并不能预先保证微信可访问；必须在真实手机与真实网络上验证。

至少由 3 名不同网络环境的测试者完成：

| 测试项 | 通过标准 |
| --- | --- |
| 微信聊天内点击链接 | 不出现安全拦截、空白页或循环跳转 |
| 页面加载 | 15 秒内加载完成，封面和题目可见 |
| 填写体验 | 单选、多选、评分题、开放题均可操作 |
| 提交 | 显示成功提示，后台出现对应测试答卷 |
| 管理后台 | 仅管理员本人能够登录 |

记录测试日期、机型、网络、结果和截图；若微信访问不稳定，暂停大规模分发并改用国内问卷平台作为临时收集通道。

## 6. 自动备份与恢复

### 6.1 备份策略

- 频率：每日一次；初始计划为中国标准时间 02:15（Cron 表达式为 UTC 前一日 `15 18 * * *`）。
- 内容：`survey_responses` 全量快照，包含答卷 ID、题目版本、提交时间和答案 JSON。
- 存储：仅写入私有 R2 Bucket。
- 加密：Worker 使用 `BACKUP_ENCRYPTION_KEY` 对快照进行 AES-256-GCM 加密后写入 R2。
- 保留建议：每日备份保留 30 天；每月第一个备份保留 12 个月。
- 校验：每月随机恢复一份备份到本地临时文件，确认答卷数与数据库记录相符。

### 6.2 恢复原则

1. 先下载需要恢复的 `.json.enc` 文件到本地受控目录。
2. 使用项目的 `scripts/decrypt-backup.mjs` 和备份密钥解密。
3. 先在独立的恢复数据库验证数据，不直接覆盖生产数据库。
4. 核对答卷数、提交时间和 JSON 结构后，再决定是否恢复生产环境。

> [!danger] 不可执行的操作
> 不要把备份密钥粘贴到群聊、Issue、GitHub Actions 日志或 Obsidian 同步库；不要为“方便下载”将 R2 Bucket 设为公开。

## 7. 日常运维

### 每周

- [ ] 登录后台，确认最近答卷可读、导出正常。
- [ ] 查看 Worker 错误日志，处理提交失败或异常峰值。
- [ ] 检查 R2 是否产生最新备份对象。

### 每月

- [ ] 进行一次备份恢复演练。
- [ ] 导出一份加密归档副本到学校批准的私有存储。
- [ ] 更新依赖并在测试地址验证。
- [ ] 复核匿名说明、题目版本和数据用途是否仍准确。

### 问卷结束时

1. 在首页将问卷状态改为“已结束”，保留研究说明。
2. 导出原始 CSV，记录导出日期和问卷版本。
3. 将分析用数据与原始答卷分开保存。
4. 按研究伦理与学校要求确定保留期、访问权限与销毁方式。

## 8. 变更记录

| 日期 | 变更 | 责任人 | 影响 |
| --- | --- | --- | --- |
| 2026-09-07 | 建立 Cloudflare 部署与备份方案 | CLKG 研究团队 | 首次上线准备 |

## 9. 相关文件

- Web App：`07_researcher_survey/`
- D1 migration：`07_researcher_survey/drizzle/0000_right_wolverine.sql`
- 部署配置模板：`07_researcher_survey/wrangler.jsonc.example`
- 备份恢复脚本：`07_researcher_survey/scripts/decrypt-backup.mjs`
