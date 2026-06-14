# FORK.md — 本 Fork 的定制规范与维护手册

> **这是什么**：本仓库是从 [microsoft/qlib](https://github.com/microsoft/qlib)
> fork 而来的**自用定制版**。本文件是本 fork 的"单一事实来源"——记录我们和上游的差异、
> 定制规范、同步上游的操作流程、以及本地（WSL + RTX 5090）运行配置。
>
> **读者**：未来的我，以及任何进入本仓库的 agent（Claude Code / Codex 等）。
> **维护**：每次新增/修改定制，或同步一次上游，都要回来更新对应章节 + 底部"最后更新"。
>
> **姊妹文档**：本机工作站手册见 `~/CLAUDE.md`；本仓库 agent 入口见根目录 `CLAUDE.md`。
> 本 fork 的体例与命名沿用我们另一个 fork [`TradingAgents`](https://github.com/ybwbqg9379/TradingAgents) 的 `FORK.md`。
>
> **最后更新**：2026-06-14（Phase 2 完成：全 S&P500 自有 Massive 数据跑通 2021–2026 回测）

---

## 🚀 接手指南（新 session / 新 agent 从这里开始）

> 这是交接入口——只放**指针**，不复制状态（所以不会过时）。按顺序看三处即可上手：
>
> 1. **现在做到哪、下一步做什么** → 看 **§10 路线图状态表**（Phase 0–2 已完成；下一步 = Phase 3 自定义因子/模型/策略）。
> 2. **怎么把环境跑起来** → §5.1 激活 `.venv`；跑任何 `qrun` 前先 `export MLFLOW_ALLOW_FILE_STORE=true`（§9.1）。
> 3. **动手前必读的规矩** → §2 定制规范（扩展不改上游）、§3 commit 门禁（`Fork:` trailer；钩子没启用先 `./scripts/setup-hooks.sh`）。
>
> 自动加载的上下文已经替你记住了大部分：根目录 `CLAUDE.md`（agent 入口）+ 4 条跨 session 记忆
> （fork 策略 / 扩展点 / 本地环境 / 数据 collector）。**本文件 = 单一事实来源**，不另设 HANDOFF 文档以免重复漂移。

---

## 0. 本 Fork 的定位（先读这一节）

- **目的**：自用。在本地（WSL2 + RTX 5090 + llama.cpp）跑这个 AI 量化研究平台，
  并按需加入我们自己的能力（因子 / 模型 / 策略 / 数据源）。
- **主战场**：**美股**。我们持有 **Alpha Vantage** 和 **Massive（原 Polygon）** 数据订阅。
  中国市场 / 自有数据源是次要目标。
- **不提 PR**：我们**不打算**把改动贡献回上游 `microsoft/qlib`。
  原因：(1) 没必要；(2) 上游不一定接受。
  → 推论：**无需保持 `main` 的"上游纯净度"**，`main` 就是我们的定制主线。
- **核心诉求**：既要**吃到上游更新**，又要**保留自己的定制**，还不能让两者打架。
  - 打架的唯一根源 = **合并冲突** = 我们和上游改了**同一行代码**。
  - 因此所有规范的本质，都是"降低与上游改同一行的概率"，而**与提不提 PR 无关**。
  - 好消息：qlib 的扩展性极好（见 §2），绝大多数定制都能**完全不碰上游文件**。

---

## 1. 当前状态（与上游的关系）

| 项 | 值 |
|---|---|
| 上游 (`upstream`) | https://github.com/microsoft/qlib |
| 我们的远程 (`origin`) | https://github.com/ybwbqg9379/qlib |
| Fork 基点 commit | `d5379c52` (`docs: replace broken RD-Agent demo links in README (#2150)`) |
| 当前与上游差异 | 仅治理脚手架（FORK.md / CLAUDE.md / .githooks / qlib/custom/ 空包）；**无任何功能性定制** |

> 上游本身用 Conventional Commits（commitlint 卡 PR 标题），所以你在 `git log` 里看到的
> `feat:` / `fix:` 风格 commit **都来自上游**，不是我们的定制。我们的 commit 靠 `Fork:` trailer 区分（见 §3）。

---

## 2. 定制规范（动手前必读）

### 原则一：扩展优于修改（最重要）

qlib 有一个贯穿全局的"**配置即扩展**"机制：任何 workflow YAML 里写
`class` + `module_path` + `kwargs`，`init_instance_by_config()`
（`qlib/utils/mod.py`）就会去 import 你指定的**任意类**并实例化。
→ 模型 / 数据集 / 数据 handler（因子）/ 策略 / processor / record **全都能指向我们自己的类**，
**完全不改上游代码**。这是本 fork 最重要的扩展点。

| 想做的事 | 落点（无需改上游文件） |
|---|---|
| 自定义**因子/特征** | `qlib/custom/data/` 里写 `DataHandler`/继承 `Alpha158` 子类，YAML `module_path: qlib.custom.data.xxx` 引用；或用表达式引擎（`Ref/Mean/Std/...`）直接在 handler 里写因子 |
| 自定义**模型** | `qlib/custom/model/` 里继承 `qlib.model.base.Model`（实现 `fit`/`predict`），YAML 引用 |
| 自定义**策略** | `qlib/custom/strategy/` 里继承 `qlib.contrib.strategy.BaseSignalStrategy`，YAML 引用 |
| 自定义 **processor/record** | 同理放 `qlib/custom/`，YAML `module_path` 引用 |
| 接**外部数据源**（AV / Polygon） | 新建 `scripts/data_collector/<vendor>/`（仿 `yahoo/`）产出 CSV → `scripts/dump_bin.py` 转 `.bin`（见 §5.3） |
| 改模型/数据/参数 | 全在 workflow YAML（`examples/` 里建我们自己的 config，不改上游 benchmark） |
| 我们自己的独立逻辑 | 新建 `qlib/custom/`（本 fork 约定的私有子包，已建 `__init__.py`） |

> **为什么 custom 放 `qlib/custom/` 而不是顶层 `qlib_custom/`**：`pip install -e .` 后
> setuptools 会自动收录 `qlib.custom`，YAML 里 `module_path: qlib.custom.xxx` 永远可 import；
> 且上游永不会创建 `qlib/custom/` 目录 → 零冲突。它是**新增子包**，不是对上游文件的修改。

### 原则二：必须改上游文件时，把改动做到最小且可追踪
1. 真正的逻辑抽到独立模块（如 `qlib/custom/...`），上游文件里只留**一行调用**。
2. 在改动处用统一标记，便于 `grep` 一键找出我们所有的侵入式改动：
   ```python
   # [FORK] 原因简述；详见 FORK.md §6 / qlib/custom/xxx.py
   ```
3. 改完后到 §6 差异清单登记一条。

### 原则三：每条定制都登记
任何会让我们偏离上游的改动，都到 **§6 差异清单**记一行：做了什么 / 为什么 / 碰了哪些文件。
这样下次 merge 上游冲突时，能立刻判断每处冲突该怎么取舍。

### 快速自检：找出当前所有侵入式改动
```bash
grep -rn "\[FORK\]" --include="*.py" .          # 所有标记的侵入式改动
git diff --stat upstream/main..main             # 我们改/加了哪些文件
git log --oneline upstream/main..main           # 我们的全部定制 commit
git log --grep '^Fork:' --oneline               # 同上，靠 commit 的 Fork: 标记（见 §3）
```

---

## 3. Commit 规范与门禁

上游**已经**用 **Conventional Commits**（`.commitlintrc.js`，commitlint 卡 PR 标题，header ≤100 字符）。
我们**沿用同一套主题格式**（同步上游后 `git log` 风格统一），并加一条 `Fork:` trailer
把我们自己的 commit 和上游区分开。**这条规范由一个本地（非 CI）git 门禁强制执行**，不合规的 commit 会被拒绝。

### 3.1 格式
```
<type>(<scope>): <description>

<body，可选>

Fork: <一句话说明这条改动为什么是我们加的>   ← 本 fork 的强制标记（见 3.2）
```

- **type**（沿用上游 commitlint）：`feat` | `fix` | `docs` | `refactor` | `perf` | `test` | `build` | `ci` | `chore` | `revert` | `style`
- **scope**：小写子系统名，如 `data` `model` `strategy` `backtest` `workflow` `dataset` `contrib`
  `cli` `config` `rl` `docs` `deps`；本 fork 自己的横切改动可用 `custom` 或 `fork`
- **description**：祈使句、不加句号；建议 ≤72 字符（门禁硬上限 100）
- 引用上游 issue 时沿用上游写法，在描述末尾加 `(#123)`

### 3.2 我们的 commit 如何与上游区分
**约定：凡是我们自己 author 的 commit，都必须带一个 `Fork:` trailer**（body 里单起一行，
`Fork: <原因>`）。

- 为什么用 trailer 而不是改 type/scope：保持和上游**完全一致**的 `type(scope): ...` 主题行，
  历史风格统一；区分信息放在 footer，既不污染主题、又能稳定 `grep`。
- 好处：`git log --grep '^Fork:'` 永远精确列出"我们加的东西"，即使多次 merge 之后我们的
  commit 和上游 commit 在 `git log` 里交错，也一眼可辨。
- 上游 commit 是通过 `git merge upstream/main` **合并**进来的，我们并不 author 它们，
  所以它们不带 `Fork:`，门禁也会放行 merge commit（见下）。

示例：
```
feat(custom): add Polygon US-equity data collector

Fork: 上游无 Polygon 数据源，美股是本 fork 主战场
```

### 3.3 门禁（本地 git hook，强制、非 CI）
门禁是一个版本化的 `commit-msg` 钩子，位于 **`.githooks/commit-msg`**。它会拒绝：
1. 主题行不符合 `type(scope): description`；
2. 主题超过 100 字符；
3. 缺少 `Fork:` trailer。

`merge` / `revert` / `fixup!` / `squash!` 这类自动生成或非我们 author 的消息会被自动放行
（上游 commit 正是经由 merge 进来）。

**启用（每个 clone 一次性操作）**——git 钩子不随 clone 分发，需要把 git 指到 `.githooks/`：
```bash
./scripts/setup-hooks.sh            # 等价于 git config core.hooksPath .githooks
git config --get core.hooksPath     # 验证，应输出 .githooks
```
> **给 agent 的提示**：进入本仓库后若 `git config --get core.hooksPath` 为空，
> 先跑 `./scripts/setup-hooks.sh` 再开始工作。
>
> 真正的紧急情况可用 `git commit --no-verify` 绕过，但**不鼓励**，且仍要事后补登记 §6。

---

## 4. 同步上游的标准流程（SOP）

我们用的是 **"`main` 即定制主线"** 模式（不开独立定制分支，因为不提 PR）。
定期把上游合并进来即可：

```bash
# 1. 确保工作区干净
git status

# 2. 拉取上游最新
git fetch upstream

# 3. 看上游领先了多少、有哪些 commit
git log --oneline main..upstream/main

# 4. 合并进我们的 main（用 merge，不用 rebase——保留清晰的合并历史）
git merge upstream/main

# 5. 若有冲突：结合 §6 差异清单逐个解决，保留我们的定制意图
#    解决后：git add -A && git commit

# 6. 跑一遍冒烟测试（见 §7）确认没被上游改动弄坏

# 7. 推到我们自己的 origin
git push origin main

# 8. 回到本文件更新 §1 的"Fork 基点 commit"和底部"最后更新"
```

> **为什么用 merge 不用 rebase**：我们不提 PR，不需要线性历史；merge 能完整保留
> "某次同步上游"这个事件，将来排查问题更清楚，也不会重写已推送的历史。
>
> **冲突面极小**：因为定制几乎全在 `qlib/custom/` + 我们自己的 YAML + `scripts/data_collector/<vendor>/`，
> 这些路径上游不会动。真正可能冲突的只有少数带 `[FORK]` 标记的侵入式改动（grep 一下即知）。

---

## 5. 本地运行配置（WSL + RTX 5090）

### 5.1 安装
```bash
# 仓库根目录（包名 pyqlib，import qlib；本机用 Python 3.12 + 专用 venv）
python3 -m venv .venv && .venv/bin/pip install -U pip setuptools wheel setuptools_scm
.venv/bin/pip install -e .   # 装核心 + 自动编译 Cython 扩展（约 2–3 分钟）
./scripts/setup-hooks.sh     # 启用 commit 门禁（见 §3.3），每个 clone 一次
```
- 本机已建好 `.venv/`（已 gitignore）。后续命令都用 `.venv/bin/python` / `.venv/bin/qrun`。
- **⚠️ 必须设 `MLFLOW_ALLOW_FILE_STORE=true`**：新版 mlflow（3.13）把文件型 tracking 后端列为
  "maintenance mode" 并默认报错，而 qlib 用的正是文件后端。跑 `qrun` 前 export 它，否则在
  实验初始化处崩。详见 §9.1。

> Lint/格式沿用上游：black（120 列）+ pylint + flake8 + mypy；`make lint` 一把跑。
> 测试：`cd tests && pytest . -m "not slow"`（见 §7）。

### 5.2 拉数据 + 跑一个 benchmark（先验证环境通）
```bash
# 美股日线示例数据（上游提供，~450MB，解压到 ~/.qlib/qlib_data/us_data）
.venv/bin/python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/us_data --region us
# 跑我们的美股 benchmark（见 §5.2 末）
MLFLOW_ALLOW_FILE_STORE=true .venv/bin/qrun examples/fork/workflow_config_lightgbm_alpha158_us.yaml
```
qlib 通过 `qlib.init(provider_uri=..., region="us")` 指向数据目录；美股 region 已内建（`REG_US`）。

> **美股数据要点**（实测 2026-06-14）：日历 1999-12-31 ~ **2020-11-10**（数据到 2020 年底为止，
> 配 YAML 的 test 区间别超）；8994 个 symbol；universe 文件有 `sp500.txt` / `nasdaq100.txt` / `all.txt`；
> 基准指数 symbol 用 **`^GSPC`**（标普500，数据里有；另有 `^ndx` `^dji`、ETF `spy`）。
> 上游 benchmark 的 YAML 都是 CN（csi300 + 10% 涨跌停 `limit_threshold: 0.095`），**不能直接拿来跑美股**；
> 我们的美股 config 在 `examples/fork/workflow_config_lightgbm_alpha158_us.yaml`（market=sp500、benchmark=^GSPC、去掉涨跌停）。

### 5.3 接我们的数据源（Alpha Vantage / Massive）✅ 已建好并实测（Phase 2）
qlib 数据是**文件式 `.bin`**，外部数据走 **collector → normalize → dump_bin** 三步。
我们已新建两个 collector（仿上游 `yahoo/`，**全是新增文件、不改上游**）：

| Vendor | 目录 | key（`.env`） | 说明 |
|---|---|---|---|
| **Massive**（原 Polygon） | `scripts/data_collector/massive/` | `MASSIVE_API_KEY`（`POLYGON_API_KEY` 兼容） | 美股 OHLCV+vwap，日线/分钟；REST `/v2/aggs` |
| **Alpha Vantage** | `scripts/data_collector/alpha_vantage/` | `ALPHA_VANTAGE_API_KEY` | 美股，日线(复权,带 factor)/1min；有限速 |

**⚠️ Massive 域名迁移**：Polygon.io 已于 **2025-10-30 更名 Massive**，REST host 现为
`https://api.massive.com`（旧 `api.polygon.io` 在 2026 迁移窗口内仍可用，同 key、接口不变）。
默认已指向新域名，可用 `.env` 的 `MASSIVE_BASE_URL` 覆盖。

**配 key**：`cp .env.example .env`，填 `MASSIVE_API_KEY` / `ALPHA_VANTAGE_API_KEY`（`.env` 已 gitignore，
collector 自动加载）。各 vendor 的 `README.md` 有完整命令。三步范式（以 Massive 日线为例）：
```bash
cd scripts/data_collector/massive
# 1) 拉取 → source/*.csv（--symbols 可给逗号串/qlib instrument 文件路径/省略=冒烟集）
python collector.py download_data --source_dir ~/.qlib/stock_data/massive/source_1d \
  --interval 1d --start 2018-01-01 --end 2024-12-31 \
  --symbols ~/.qlib/qlib_data/us_data/instruments/sp500.txt --delay 0.2 --max_workers 1
# 2) 规整 → normalize/*.csv（加 factor/change 列）
python collector.py normalize_data --source_dir ~/.qlib/stock_data/massive/source_1d \
  --normalize_dir ~/.qlib/stock_data/massive/norm_1d --interval 1d
# 3) dump → .bin（⚠️ 必须 --data_path，且 --include_fields 只列数值列，否则文本 symbol 列报 float 错）
python ../../dump_bin.py dump_all --data_path ~/.qlib/stock_data/massive/norm_1d \
  --qlib_dir ~/.qlib/qlib_data/us_data_massive --freq day \
  --include_fields open,high,low,close,volume,vwap,factor,change
# 用：qlib.init(provider_uri="~/.qlib/qlib_data/us_data_massive", region="us")
```
分钟级：三步都换 `--interval 1min` + dump 用 `--freq 1min`（AV 1min 按月分页、注意限速）。

> **Massive 是无限套餐**：可随便调用——不用 `--delay`，`--max_workers 16` 并发拉，
> 直接拉全 sp500 + 长历史 + 分钟级都没关系。AV 才需要省着用（免费 ~25 req/day）。

> **实测（2026-06-14）**：两个 collector 都端到端跑通——AAPL/MSFT 2024 日线 download→normalize→dump→
> `D.features` 读回价格正确；AV 的 `factor`（=adjclose/close）随分红正确变化。两条踩坑（dump 用
> `--data_path` 不是 `--csv_path`；必须 `--include_fields`）已写进 README 与 §9.4。
> 上游**没有** AV/Massive 集成（grep 确认），这是本 fork 补的第一块自有能力。

### 5.4 接本地 llama.cpp（qlib 本体不需要 LLM）
qlib 框架本身**不调用 LLM**；LLM 用在姊妹项目 **RD-Agent**（自动因子挖掘/模型优化）。
若要本地跑 LLM，按 `~/CLAUDE.md` 启动 llama.cpp（`~/start-llamacpp.sh qwen`，OpenAI 兼容端点
`http://localhost:8080/v1`），RD-Agent 或我们自己的脚本把 `base_url` 指过去即可。
> **显存约束（见 `~/CLAUDE.md`）**：32GB 单卡同一时刻只能跑一个大模型。

### 5.5 运行
```bash
qrun <workflow_config.yaml>            # 标准工作流入口（qlib/cli/run.py）
# 或在 Python 里 import qlib; qlib.init(...); 自己编排 model/dataset/strategy
```

---

## 6. 与上游的差异清单（Changelog of Divergence）

> 每条定制登记一行。

| 日期 | 定制内容 | 为什么 | 落点（文件） | 是否侵入上游文件 |
|---|---|---|---|---|
| 2026-06-14 | 建立 fork 治理脚手架 | 把 TradingAgents 那套 fork 规范移植到 qlib | `FORK.md` `CLAUDE.md` `.githooks/commit-msg` `scripts/setup-hooks.sh` `qlib/custom/__init__.py`（全为新增文件） | 否（纯新增） |
| 2026-06-14 | 美股 LightGBM/Alpha158 workflow config | 上游 benchmark YAML 全是 CN（csi300+涨跌停），美股跑不了；这是 Phase 1 跑通环境的 config | `examples/fork/workflow_config_lightgbm_alpha158_us.yaml`（新增） | 否（纯新增） |
| 2026-06-14 | gitignore 加 `.venv/` `mlruns/` | 本机 dev 产物不入库 | `.gitignore`（追加 `[FORK]` 块） | 是（append-only，冲突风险极低） |
| 2026-06-14 | Massive（原 Polygon）数据 collector | 美股主战场,上游无此源;含日线/分钟 | `scripts/data_collector/massive/`（collector.py+README，新增） | 否（纯新增） |
| 2026-06-14 | Alpha Vantage 数据 collector | 同上,另有复权/基本面 | `scripts/data_collector/alpha_vantage/`（collector.py+README，新增） | 否（纯新增） |
| 2026-06-14 | API key 占位符模板 | 两个 collector 的 key 入口 | `.env.example`（新增,committed）+ `.env`（gitignored,本机填） | 否（纯新增） |

<!--
登记模板：
| 2026-06-XX | 加了 Polygon 数据源 | 上游不支持，美股主战场 | scripts/data_collector/polygon/collector.py（新增） | 否 |
| 2026-06-XX | 自定义动量因子集 | 试自己的 alpha | qlib/custom/data/momentum_handler.py（新增）+ examples 下我们的 YAML | 否 |
| 2026-06-XX | 改了某上游文件一行 | 适配 XXX | qlib/yyy.py 一行调用[FORK] + qlib/custom/zzz.py | 是 |
-->

---

## 7. 冒烟测试（同步上游后/改动后跑一遍）

```bash
# 代码风格（上游 CI 会跑）
make black                       # 或 black qlib qlib/custom -l 120
make flake8 && make pylint       # 视改动范围

# 单元测试（排除 slow）
cd tests && pytest . -m "not slow"
pytest tests/test_dump_data.py   # 若动了数据/collector
pytest tests/storage_tests/      # 若动了 storage/provider

# 端到端最小验证：跑一个 benchmark，确认没被上游改动弄坏
qrun examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml
```

---

## 8. 维护本文件

- **新增/修改定制** → 更新 §6 差异清单（必要时 §2 原则）。
- **同步一次上游** → 更新 §1 的"Fork 基点 commit" + 跑 §7 冒烟测试。
- **改了本地运行方式/数据源/端口** → 更新 §5。
- **改了 commit 规范或门禁** → 更新 §3 + `.githooks/commit-msg`。
- **跑出新的本地运行经验/坑** → 记到 §9。
- **推进某条路线图** → 更新 §10 的状态表（进来先看它知道做到哪）。
- 每次改完，更新顶部"最后更新"日期。

---

## 9. 本地运行的已知问题与经验

> 首次端到端跑通记录（2026-06-14，US LightGBM/Alpha158，`.venv` + Python 3.12）。

### 9.1 mlflow 文件后端默认报错 → 必须 `MLFLOW_ALLOW_FILE_STORE=true`
- 现象：`qrun` 在实验初始化处崩，`MlflowException: The filesystem tracking backend ... is in maintenance mode`。
- 原因：`pip install -e .` 装到 mlflow 3.13（最新），它把文件型 tracking 后端（qlib 默认用的 `./mlruns`）列为维护模式并默认抛错。
- 解法：跑 `qrun`/工作流前 `export MLFLOW_ALLOW_FILE_STORE=true`（mlflow 自己给的 opt-out）。**这是当前唯一的环境拦路虎**。
- 备选（更稳，未采用）：把 mlflow 钉到旧版（如 `pip install 'mlflow<3'`）。先用 env 变量，简单。

### 9.2 首跑结果（环境验证用，非策略结论）
- 流水线完整跑通：数据 → Alpha158（158 因子）→ LGBModel 训练 → IC 分析 → TopkDropout 回测 → 组合报告，全程 < 1 分钟。
- 信号很弱：`IC≈0.0066`、`Rank IC≈0.0047`；策略**跑输**买入持有标普（excess return 含成本 **-5.2%/年**，benchmark `^GSPC` 同期 +12.1%/年，最大回撤 -38%（含 2020 covid））。
- **这是预期内的**：用的是上游**为 CN 调的超参** + 默认 Alpha158 + 2017–2020 测试段，目的只是验证环境，不是策略结论。调参/换因子是后续 Phase 3 的事。

### 9.3 无害警告（可忽略）
- `$close field data contains nan`：sp500 成分里有退市/缺数据的 symbol，回测自动跳过。
- `load calendar error: freq=day, future=True; return current calendar!`：回测想要"未来日历"，没有就用当前日历，正常。
- `Gym has been unmaintained ... does not support NumPy 2.0`：本机装的是 numpy 2.4，gym 只在 RL 模块用到，不跑 RL 就无影响（要跑 RL 需按上游 `rl` extra 钉 `numpy<2`）。

### 9.5 自有数据首跑（Phase 2 收尾，2026-06-14）
- 用 Massive 拉全 S&P500（universe 文件 746 符号 → 734 个有数据；ABS/BS/DJ 等老退市票 Massive 无数据，正常跳过），
  日线 2008-01-02 ~ **2026-06-12**，无限套餐 `--max_workers 16 --delay 0`，**约 30 秒拉完**。
- dump 成 `~/.qlib/qlib_data/us_data_massive`（734 instruments，日历到 2026-06-12）。
- 跑 `examples/fork/workflow_config_lightgbm_alpha158_us_massive.yaml`（market=all、benchmark=SPY、test=2021–2026）：
  完整闭环通。benchmark SPY 年化 +13.75%（最大回撤 -27%）；策略超额含成本 ≈ **-0.07%/年**（基本追平 SPY），
  不含成本 +0.9%/年；IC≈0.0013。
- **定性同 §9.2**：仍是公开 Alpha158 + 为 CN 调的超参，结果≈市场、非 alpha。意义在于**自有新鲜数据的闭环通了**；
  做出超额是 Phase 3（自有因子/调参）的事。

### 9.4 dump_bin 自有数据的两个坑（Phase 2 实测）
- **参数名是 `--data_path`，不是 `--csv_path`**（上游 yahoo README 写法易误导，给错就只打印 help）。
- **必须 `--include_fields open,high,low,close,volume,...`**：dump_bin 默认把 CSV 里**每一列**都当数值
  特征 dump，会把文本 `symbol` 列转 float → `ValueError: could not convert string to float: 'AAPL'`。
  用 `--include_fields` 只列数值列即可。两个 collector 的 README 已用正确命令。

---

## 10. 路线图

> **这是跨 session 的持久路线图**——每个 session 进来先看「状态」表，知道做到哪、接着做什么。
> 状态图例：☐ 未开始 ／ ◐ 进行中 ／ ☑ 完成

| Phase | 内容 | 状态 | 验收标准 |
|---|---|---|---|
| **0 脚手架** | FORK.md / CLAUDE.md / commit 门禁 / `qlib/custom/` 空包 | ☑ 完成 | 文档就位；`./scripts/setup-hooks.sh` 生效 |
| **1 跑通环境** | 装好 + 拉美股示例数据 + 跑一个 benchmark | ☑ 完成（2026-06-14） | `qrun examples/fork/...us.yaml` 端到端出回测/组合报告（见 §9.2）；`.venv` + Python 3.12 |
| **2 接自有数据** | AV / Massive collector → dump_bin → 美股自有数据集 | ☑ 完成（2026-06-14） | 两个 collector 实测通过；全 sp500 日线 2008–2026 拉好 dump 成 `us_data_massive`；用自有新鲜数据跑通 2021–2026 回测（§9.5）。☐ 选做：批量分钟级、基本面 |
| **3 自定义因子/模型/策略** | 在 `qlib/custom/` 写我们自己的 handler/model/strategy + YAML | ☐ 未开始 | 自定义类经 `module_path` 跑通一条完整 workflow |

### 10.0 为什么要做这些 Phase（实际意义 — 进来先读这节，别把它当纯任务清单）

**先认清 Phase 1 那条 demo 的两处"假"**，正好对应 Phase 2 / 3 要修的东西：

| Phase 1 demo 里 | 真实情况 | 谁来修 |
|---|---|---|
| 数据 = 上游 Yahoo 样本，**只到 2020-11-10**，免费数据有复权/缺口/幸存者偏差 | 我们付费买了 **AV + Polygon**，新鲜、干净、point-in-time、有基本面/分钟级 | **Phase 2** |
| 因子 = 公开 Alpha158，模型 = 为 A 股调的超参 | 公开因子 = **零超额收益**（早被市场套利掉），需要**我们自己的因子/模型** | **Phase 3** |

→ 一句话：**Phase 1 证明"机器能转"，Phase 2 给它加"真燃料"，Phase 3 才是"我们真正要造的东西"。**

**Phase 2（自有数据）的意义：**
- *功能*：① 能研究**当下市场**（现在的数据停在 2020，回测的是不含 2022 熊市 / 2023–24 AI 牛市 / 加息周期的"古代行情"）；② 数据质量 = 回测可信度（垃圾进垃圾出，付费源才可信）；③ 是"能交易"的前提（数据停在 2020 就永远只能回测，谈不上 paper/实盘）。
- *战略*：模型是大路货，**数据 + 因子才是护城河**。且这条美股数据管道对**两个 fork 复用**——qlib 和 TradingAgents 都吃同一份 AV/Polygon 数据，做一次两边受益。

**Phase 3（自定义因子/模型/策略）的意义：**
- *功能*：前面全是基础设施，**Phase 3 才是"做量化研究"本身**。自定义因子 = 我们对"什么预测收益"的假设 = **alpha 来源**；自定义模型/策略 = 建模与仓位/风控的自由度。用公开因子人人平手，用自己的因子才有 edge。
- *研发*：它搭起一个**可重复的研究迭代闭环**——`想法 → 写成因子 → qrun 回测 → 看 IC/夏普/回撤 → 证伪或保留 → 下一个想法`。靠 `qlib/custom/` + 不改上游的扩展机制，每个新想法 = 加一个文件 + 一份 YAML，几分钟出结果，把"灵感"工业化成"可批量验证的研究"。
- *战略*：它是**未来 LLM 自动化的插槽**。要让本地 llama.cpp / RD-Agent 路线**自动挖因子**，LLM 生成的因子得有地方插入、有框架自动回测——Phase 3 的脚手架正是 LLM 操作的底座。**Phase 3 = 人工研究循环 + 未来 LLM 自动研究循环 共用的同一套地基。**

**两个 fork 的协同（为什么这套对整个研发有复利）：**

| | qlib（本项目） | TradingAgents（姊妹 fork） |
|---|---|---|
| 风格 | **系统化**：全市场因子 + 组合 + 回测 | **判断式**：LLM 像分析师逐票决策 |
| 共享 | ← **AV/Polygon 美股数据（Phase 2）** → | 同一套数据 |
| 协同 | Phase 3 的自定义因子/信号可作 TradingAgents agent 的输入工具 | TradingAgents 选候选 → qlib 系统化回测验证 |

→ 终点：把这个 fork 从"能跑微软的 demo"变成"**我们自己的、能持续产出 alpha 研究、并可叠加 LLM 自动化的本地美股平台**"。

### 设计要求 / 约束
- **不改上游**：定制全部经 `qlib/custom/` + YAML `module_path` + `scripts/data_collector/<vendor>/`。
- **美股优先**：`region="us"`；数据用我们订阅的 AV / Polygon，而非默认 yfinance。
- **定性**：量化策略业绩声称水分大、非确定性；回测≠实盘，任何决策当假设而非策略。
