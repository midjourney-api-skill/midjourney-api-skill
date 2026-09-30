# Midjourney-API Skill

> 通过 **HTTP API** 调用 `midjourney-api.com` 生成图片的 Agent Skill（文生图 / AI 绘画）。
> **不依赖 Discord、不需要 Discord 账号、不使用 `/imagine` 命令。**

[English](#english) · 中文

---

## 这是什么 / What is this

一个可直接被 Agent 平台（**Manus**、**WorkBuddy/CodeBuddy**、兼容 Agent Skills 规范的运行时）加载的技能。它把「提交 prompt → 轮询任务 → 下载图片」这套**异步**流程封装进一个零依赖的 Python CLI，Agent 无需自己重造 HTTP + 轮询逻辑。

- 覆盖端点：`submit-jobs`（创建任务）、`job-status`（轮询结果）
- 自带 CLI：`generate` / `submit` / `status` / `poll` 四个子命令
- 纯标准库（`urllib`），**无需 `pip install`**
- 已处理两个真实坑：Cloudflare 拦截（默认带浏览器 UA）、官方 CDN 防盗链（自动回退镜像）

## 前置条件 / Requirements

- Python 3.8+（仅用标准库）
- 一个 `MIDJOURNEY_API_KEY`，在 https://midjourney-api.com/dashboard 申请

```bash
export MIDJOURNEY_API_KEY="你的key"   # 也可用 MJ_API_KEY 作为兜底
```

> ⚠️ 密钥从环境变量读取，**不要写入代码或提交到仓库**。

## 一键使用 / Quick start

```bash
python3 scripts/midjourney.py generate \
  --prompt "a serene lake at sunset --ar 16:9" \
  --out ./midjourney_out
```

该命令会：提交任务 → 每 10s 轮询（默认最多 20min）→ 把网格图与 4 张单图下载到 `--out` 目录。

其他子命令：

```bash
# 只提交，拿 taskId
python3 scripts/midjourney.py submit --prompt "a cyberpunk cat --niji 6"

# 轮询直到完成并下载
python3 scripts/midjourney.py poll --task-id <taskId> --out ./out

# 只查原始状态（不下载）
python3 scripts/midjourney.py status --task-ids <id1> <id2>
```

## 安装到 Agent 平台 / Install into an agent platform

本仓库根目录即一个合法的 skill（含 `SKILL.md`），可直接被以下方式加载：

| 平台 | 方式 |
| --- | --- |
| **Manus** | 左侧 **Skills** → **+ 添加** → **上传技能**（拖入本仓库或 `.skill`/`.zip`）或 **从 GitHub 导入** |
| **WorkBuddy / CodeBuddy** | 把本仓库放到用户级 `~/.codebuddy/skills/midjourney-api/`，或项目级 `.workbuddy/skills/midjourney-api/` |
| **SkillHub** | 上架时需要 `slug`/`summary` 等扩展字段，请用 SkillHub 专用发布包（见下方说明），标准包会因缺字段被拦 |

加载后在对话中输入 `/midjourney-api`（或说「生成图片 / AI 绘画 / 文生图」）即可触发。

## 发布到 GitHub / Share via GitHub

```bash
git init
git remote add origin https://github.com/<你的用户名>/midjourney-api-skill.git
git add .
git commit -m "feat: add midjourney-api agent skill"
git push -u origin main
```

推到公开仓库后，其他人即可用 Manus 的「**从 GitHub 导入**」或 WorkBuddy 的项目级技能目录一键使用。也可顺手提交到社区目录 [awesome-agent-skills](https://github.com/)。

> **关于 SkillHub**：SkillHub 的概述（overview）来自 frontmatter 的 `summary` 字段，而本 skill 用的是 Agent Skills 标准格式（仅 `name`/`description`/`license`）。若要上架 SkillHub 并自定义概述，请用附带 `slug`/`displayName`/`version`/`summary` 的 SkillHub 专用包，不要直接用本仓库（否则平台会 AI 生成一段可能失真的概述）。

## 目录结构 / Repository layout

```
midjourney-api/
├── SKILL.md                  # 技能主文件（Agent 读取的指令 + 触发词）
├── scripts/
│   └── midjourney.py         # 零依赖 CLI：generate / submit / status / poll
├── references/
│   └── api_reference.md      # 完整字段 / 响应 / 错误码参考
├── README.md                 # 本文件
├── LICENSE                   # MIT
└── .gitignore                # 忽略密钥、产物、缓存
```

## API 速览 / API at a glance

完整字段见 [references/api_reference.md](references/api_reference.md)。

| 动作 | 端点 | 说明 |
| --- | --- | --- |
| 创建任务 | `POST /midjourney/v1/submit-jobs` | 入参 `prompt`(必填)、`mode`、`timeout`、`hookUrl`；返回 `data.taskId` |
| 轮询结果 | `POST /midjourney/v1/job-status` | 入参 `taskIds[]`；任务 `status`：`0`进行中 / `1`完成 / `2`失败 |

常见返回码：提交层 `0`成功 / `1001`额度不足 / `1002`并发超限(≤30)；任务层 `0/1/2`。

## 许可证 / License

[MIT](LICENSE) —— 自由使用、修改、分发，请保留版权声明。

## 免责声明 / Disclaimer

- 本 skill 调用第三方服务 `midjourney-api.com`，需自备 key 并自行承担费用。
- 仅覆盖官方文档中已稳定的 `submit-jobs` 与 `job-status` 端点；upscale / variation / blend 等上游仍标注「updating」，未实现。
- 脚本仅向官方 API 发请求，密钥仅从环境变量读取、不落盘、不回显。

---

## English

A ready-to-load Agent Skill that drives the Midjourney REST API at `midjourney-api.com` to generate images from text prompts. **No Discord, no `/imagine`, no Discord account required.** It bundles a zero-dependency Python CLI (`submit → poll → download`) so the agent never has to reimplement async polling.

**Requirements:** Python 3.8+, and a `MIDJOURNEY_API_KEY` exported as an env var.

```bash
export MIDJOURNEY_API_KEY="your-key"
python3 scripts/midjourney.py generate --prompt "a serene lake at sunset --ar 16:9" --out ./out
```

**Install:** the repo root is itself a valid skill (`SKILL.md` present). Upload the folder / `.skill` / `.zip` to Manus, drop it into `~/.codebuddy/skills/` (WorkBuddy), or import from GitHub. Type `/midjourney-api` to invoke.

**License:** MIT. See [LICENSE](LICENSE).
