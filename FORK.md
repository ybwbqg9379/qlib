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
> **最后更新**：2026-06-14（Phase 3：接入 PIT 基本面并确认 §9.11 假设——价值/质量因子把 2017–19 连亏段修到持平，正年 7/11→9/11、均值不变(+11.3%)即"更稳非更赚"；当前最优 `Alpha158CustomFund`(§9.14–9.15)。方法论=因子看gain/SHAP·业绩看多seed·稳健看滚动）

---

## 🚀 接手指南（新 session / 新 agent 从这里开始）

> 这是交接入口——只放**指针**，不复制状态（所以不会过时）。按顺序看三处即可上手：
>
> 1. **现在做到哪、下一步做什么** → 看 **§10 路线图状态表 + §9.6–§9.15 研究记录**（Phase 0–2 完成；Phase 3 已跑完一整轮研究闭环并接入 PIT 基本面：当前默认 handler `Alpha158CustomFund`，结论"更稳非更赚"。下一步候选 = 基本面因子归因/多seed复核/美股调参/自定义模型·策略）。**研究方法论铁律**：因子取舍看 gain/SHAP（非单因子 IC）、业绩对比须多 seed（单 seed ±10pp 噪声）、稳健性看滚动回测。
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
| 2026-06-14 | 第一个自定义因子 handler `Alpha158Custom` + workflow | Phase 3 起步：证明 `qlib/custom/` + YAML `module_path` 扩展机制；Alpha158 + 6 个有经济含义的自有因子 | `qlib/custom/data/handler.py`、`qlib/custom/data/__init__.py`、`examples/fork/workflow_config_lightgbm_custom_us_massive.yaml`（全新增） | 否（纯新增） |
| 2026-06-14 | 单因子 IC 归因脚本 + 剪枝实验 `Alpha158CustomLite` | Phase 3 证伪环节；归因脚本可复用；剪枝实验证伪"单因子 IC 可给树模型剪枝"（§9.7），留档 | `examples/fork/factor_ic_attribution.py`、`Alpha158CustomLite`（handler.py 内）、`examples/fork/workflow_config_lightgbm_custom_lite_us_massive.yaml`（全新增） | 否（纯新增） |
| 2026-06-14 | `GeneralPTNN` DataLoader 加 `persistent_workers` | 原代码每 epoch 重 fork `n_jobs` 个 worker，在容器里 NN 训练**验证阶段 DataLoader worker 死锁**（fork-after-threads + qlib mmap 数据，时有时无）；改成 worker 复用一次性 fork、根治死锁且保留并行 | `qlib/contrib/model/pytorch_general_nn.py`（train/valid/test 三个 DataLoader 各加 `persistent_workers=self.n_jobs>0`，`# [FORK]`） | **是**（3 处，侵入式；上游若改此文件需留意冲突） |
| 2026-06-14 | Gain/SHAP 因子归因脚本 | Phase 3 正确的归因法（替代单因子 IC）；6 因子占 19.5% SHAP，LOTTERY21 双法垫底（§9.8） | `examples/fork/factor_gain_shap_attribution.py`（新增） | 否（纯新增） |
| 2026-06-14 | gain/SHAP 剪枝版 `Alpha158Custom5`（默认） | 只砍死因子 LOTTERY21；单 seed 曾显示全项改善（§9.9），多 seed 证伪后定位为"与6因子打平、方差更低" | `Alpha158Custom5`（handler.py 内）、`examples/fork/workflow_config_lightgbm_custom5_us_massive.yaml`（新增） | 否（纯新增） |
| 2026-06-14 | 多种子重测脚本 | 证伪单 seed 业绩；坐实"组合超额单 seed 噪声±10pp，业绩对比须多 seed"（§9.10） | `examples/fork/multiseed_compare.py`（新增） | 否（纯新增） |
| 2026-06-14 | 滚动(walk-forward)回测脚本 | 跨市场状态稳健性检验；结论=正期望(7/11年正,均值+11.3%)但 regime-dependent、非全天候 alpha（§9.11） | `examples/fork/rolling_backtest.py`（新增） | 否（纯新增） |
| 2026-06-14 | Massive collector 带上限重试 | 鲁棒性修复：429 无限循环 + 5xx/超时不重试会挂死/崩溃批量拉取（§9.12 #1） | `scripts/data_collector/massive/collector.py`（改自研文件，非上游） | 否（自研文件） |
| 2026-06-14 | collector mock 单测（6 个） | 把 collector 鲁棒性从手动冒烟变成可回归验证（§9.12 #2） | `tests/test_fork_collectors.py`（新增） | 否（纯新增） |
| 2026-06-14 | 抽共享评估库 `_eval.py` | 消除 multiseed/rolling 评估逻辑重复，行为零变化（复现 +0.2539）（§9.12 #3） | `examples/fork/_eval.py`（新增）+ `multiseed_compare.py`/`rolling_backtest.py`（改自研脚本） | 否（自研文件） |
| 2026-06-14 | 因子改注册表 `CUSTOM_FACTORS` | 加因子=加一行；为未来 LLM 自动挖因子铺底座；行为零变化（§9.12 #4） | `qlib/custom/data/handler.py`（改自研文件） | 否（自研文件） |

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

### 9.6 第一个自定义因子 handler 首跑（Phase 3 起步，2026-06-14）
- handler：`qlib/custom/data/handler.py::Alpha158Custom` = 继承上游 `Alpha158`，override
  `get_feature_config()` 追加 6 个**有公开经济含义、且不与 Alpha158 重复**的自有因子
  （OVERNIGHT 隔夜收益 / MOM12_1 动量(12-1) / HI52W 52周高点 / LOTTERY21 彩票效应 /
  AMIHUD21 非流动性 / PVOL21 Parkinson 波动）。每个因子的论文出处和"为什么不重复"写在文件头注释。
- 扩展方式 = **纯新增类 + YAML `module_path` 引用，零改上游**（本 fork 的核心扩展机制首次用于因子）。
- config：`examples/fork/workflow_config_lightgbm_custom_us_massive.yaml`（与 Phase 2 那份**只差 handler**，
  便于对照）。同一份自有 Massive 数据、同一段 test(2021–2026)、同一套（仍是 CN 调的）LGBM 超参。
- **结果 vs Phase 2 纯 Alpha158 基线**：IC 0.0013 → **0.00235**；Rank IC 0.0067；
  超额收益(含成本) **-0.07%/年 → +5.74%/年**（IR 0.31）；基准 SPY +13.75%/年。最大回撤 -45%（偏高，待治理）。
- **定性**：研究闭环（想法→因子→qrun→IC/超额→留/弃）首次端到端跑通，且第一版迭代就跑赢基线。
  但仍是单次回测、IC 量级仍小、超参未为美股调、回撤偏大——把它当"管线/方法已验证"，**不是**已坐实的 alpha。
  下一步：扩因子、为美股调参、做单因子 IC 归因（看哪几个因子真有贡献）、再考虑自定义模型/策略。

### 9.7 单因子 IC 归因 + 剪枝实验：一个被证伪的假设（Phase 3，2026-06-14）
- **归因**（`examples/fork/factor_ic_attribution.py`，逐日横截面 RankIC，test 2021–2026）：
  MOM12_1 `+0.018 t=3.0`（唯一干净显著）、HI52W `+0.012 t=1.8`、AMIHUD21 `-0.010 t=-2.1`
  （显著但方向与教科书 Amihud 相反——大盘股池里"较不流动"成分股这段跑输）、
  OVERNIGHT/PVOL21/LOTTERY21 `|t|<1.3`≈噪声。
- **假设**：砍掉 3 个"噪声"因子（→ `Alpha158CustomLite`，只留 MOM12_1/HI52W/AMIHUD21）应能稳超额、降回撤。
- **结果（被证伪）**：精简版**模型 IC 反升**（0.0024→0.0034）但**组合超额(含成本)从 +5.74% 崩到 +0.38%**，
  IR 0.31→0.03，回撤 -45%→-48%（更差）。
- **教训**（重要，写下来免得重蹈）：
  1. **单因子 IC ≠ 因子在非线性树模型里的边际贡献**。PVOL21/LOTTERY21 线性/秩 IC≈0，却给
     LightGBM 提供了**交互/条件信号**（如"动量有效，除非高波动"）。用单因子 IC 给 GBM 剪枝是错方法。
  2. 回测超额由 top-50 头部票主导、方差极大，+5.7% 与 +0.4% 都是单次点估计，差异含大量噪声。
  3. "模型全样本 IC 升、组合收益降"说明全样本 IC 和被实际交易的头部票不是一回事。
- **决定**：**保留 6 因子版 `Alpha158Custom` 为当前最优**；`Alpha158CustomLite` 作为已证伪实验留档（调参后可重测）。
  正确的因子归因下一步用**训练后 LightGBM 的 gain/SHAP 特征重要性**（捕捉非线性+交互），而非单因子 IC。

### 9.8 Gain/SHAP 因子归因：正确的归因法（Phase 3，2026-06-14）
- 工具：`examples/fork/factor_gain_shap_attribution.py`——训练 6 因子模型后读 LightGBM 的
  **gain** 重要性 + **TreeSHAP**（lightgbm 内置 `pred_contrib`，无需外部 `shap` 库），
  捕捉单因子 IC 看不到的非线性/交互贡献。报告我们 6 个因子在全部 164 特征里的排名。
- **结果**（test SHAP 排名 / 占比，满分 164）：
  MOM12_1 **#1 (7.5%)**、AMIHUD21 **#2 (6.4%)**、HI52W #7、PVOL21 SHAP#11/**gain#3**、
  OVERNIGHT #15、LOTTERY21 **#49/gain#86（双垫底）**。6 因子合计占 **19.5%** 的 SHAP，
  而均分公平份额仅 3.7% → 自有因子单位贡献≈平均的 **5.3 倍**，加它们是值的。
- **坐实 §9.7 的教训**：PVOL21 单因子 IC≈噪声(t=-0.79)，但 gain 排第 3——大量用于交互切分；
  这正是上次按单因子 IC 砍它导致超额崩盘的原因。**归因要用 gain/SHAP，不能用单因子 IC。**
- **修正结论**：真正两法都垫底、可安全砍的只有 **LOTTERY21**（上次误砍了 PVOL21/OVERNIGHT）。
  下一步实验 = 只砍 LOTTERY21 重测，看能否在不伤超额的前提下略简化。
- **caveat**：valid l2 仅从 1.0 微降到 0.9975（best iter 17），整体信号弱；SHAP 占比是弱信号模型内的
  相对重要性、单次划分。方向性结论稳健，绝对数字勿当真。

### 9.9 gain/SHAP 指导的剪枝重测：方法论闭环完成（Phase 3，2026-06-14）
- `Alpha158Custom5` = 6 因子去掉 LOTTERY21（唯一 gain/SHAP 双垫底者，§9.8），其余全留
  （PVOL21/OVERNIGHT 单因子 IC 弱但被模型用于交互，§9.7 教训）。config:
  `examples/fork/workflow_config_lightgbm_custom5_us_massive.yaml`。
- **三版对照（同数据/同 test 2021–2026/同超参）**：

  | | 6 因子 Custom | 3 因子 Lite（**IC 剪枝**） | 5 因子 Custom5（**SHAP 剪枝**） |
  |---|---|---|---|
  | Rank IC | 0.0067 | 0.0073 | 0.0070 |
  | 超额(含成本) | +5.74% | **+0.38%** | **+15.30%** |
  | IR | 0.31 | 0.03 | **0.34** |
  | 最大回撤 | -45.5% | -48.3% | **-37.5%** |

- **闭环结论**：同样是剪枝，**IC 剪枝（误伤交互因子）→ 超额崩盘；gain/SHAP 剪枝（只砍真死因子）→ 全项改善**。
  坐实：树模型的因子取舍看 gain/SHAP，不看单因子 IC。**当前最优 = `Alpha158Custom5`**。
- **caveat（重要）**：Rank IC 几乎没变（0.0067→0.0070），底层信号质量基本一致；+5.7%→+15.3% 的跳变
  **主要是 top-50 组合高方差**（换因子→选票变→这次选得好），不是信号强 3 倍。稳健说法：砍 LOTTERY21
  **至少无害、很可能有益**（与 IC 剪枝的明确有害相反）；+15% 绝对值勿当真。下一步若要降方差/坐实增益：
  多随机种子或滚动 test 再评估。

### 9.10 多种子重测：+15% 被证伪为运气，单 seed 业绩不可信（Phase 3，2026-06-14）
> **本节纠正 §9.9**：§9.9 把 `Alpha158Custom5` 单 seed 的 +15.3% 当成"增益"并定其为"当前最优"，
> 多种子检验后**该结论不成立**——见下。研究记录保留 §9.9 原文 + 此纠正，体现闭环的自我证伪。

- 工具：`examples/fork/multiseed_compare.py`——同一组 10 个 seed 下**配对**跑 6 因子版和 Custom5
  （数据集各建一次复用，只换 LGBModel 的 `seed`），比较超额(含成本)的**分布**而非单点。
- **结果**：

  | handler | 超额均值 | 标准差 | 最差 | 最好 |
  |---|---|---|---|---|
  | 6 因子 `Alpha158Custom` | **+6.94%** | 10.1pp | -6.2% | +25.4% |
  | `Alpha158Custom5`（砍 LOTTERY21） | +4.05% | 6.7pp | -2.1% | +18.1% |

  配对差（Custom5−6因子）：均值 **−2.9pp ± 10.4pp**，Custom5 只在 **4/10** seed 上胜 → **裁决：噪声内，无差异**。
- **结论（重要，覆盖之前所有单 seed 业绩声称）**：
  1. **单 seed 组合超额噪声极大（±10pp）**。→ §9.6/§9.7/§9.9 里的 +5.7% / +0.4% / +15.3% **在组合层面都不可靠**，
     §9.9 的 +15.3% 是抽到分布高位的运气，Custom5 实际**并不优于** 6 因子（均值反而略低、但方差更小）。
  2. **因子取舍仍以 Rank IC + gain/SHAP 为准（它们稳）；组合业绩对比此后一律多 seed。**
  3. 正面信号：两版**跨 10 seed 均值超额都为正**（+6.9% / +4.1%），比单次幸运可信，但仍是单一 test 段 +
     公开因子 + A 股超参，**不构成 alpha**；真正稳健性检验 = 滚动/多 test 段（下一步）。
- **当前最优修正**：6 因子与 Custom5 **统计上打平**。默认用 `Alpha158Custom5`——**不因它赚更多（并没有），
  而因 LOTTERY21 按所有口径都是死因子、且 Custom5 结果方差更低**（同等收益取低方差）。

### 9.11 滚动（walk-forward）回测：正期望但强依赖市场状态，非全天候 alpha（Phase 3，2026-06-14）
- 工具：`examples/fork/rolling_backtest.py`——扩展窗口 walk-forward：test 年 Y∈{2016..2026}，
  train=[2008,Y-2]/valid=[Y-1]/test=[Y]，**每窗重建 handler**（归一化只在该窗 train 上 fit，无前视）、
  **重训**，每窗 **3 seed 平均**（§9.10 噪声教训）。handler=默认 `Alpha158Custom5`。
- **逐年超额(含成本)**：2016 **+17.8%** / 2017 −8.5% / 2018 −9.1% / 2019 −8.3% / 2020 **+42.1%** /
  2021 +1.0% / 2022 **+7.8%**(SPY −17.8% 熊市跑赢) / 2023 **+33.9%** / 2024 −9.3% / 2025 **+31.8%** / 2026* +25.4%。
- **裁决**：正超额 **7/11** 年，跨年均值 **+11.3% ± 19.6%**，最差 −9.3%(2024) → **不稳健，集中于特定状态**。
- **解读（迄今最重要的结论）**：
  1. 均值确实为正、赢多于输、连 2022 熊市都跑赢——比单段结果可信的正面信号。
  2. **但离散度极大，且有连续三年亏损段 2017–2019**（平滑大盘动量牛里我们偏动量的因子反跑输），
     正均值被少数大年（2020/2023/2025）撑起 = "集中于特定状态"。2017 上线会先连亏三年。
  3. **还原真相**：之前单段 test(2021–2026) 多数年为正，本身是相对有利窗口 → §9.6–9.10 的"+4~7%"也沾 regime 光。
- **定性**：**不是 alpha，是 regime-dependent 信号**（震荡/轮动/价值年强，平滑大盘动量牛跑输）。
  提稳健性的方向：① 加**非动量分散化因子**（基本面价值/质量——正好用上 Phase 2 选做的基本面数据）；
  ② 美股调参；③ regime 择时/降杠杆。

### 9.12 自研代码加固（架构/鲁棒性/可维护性/扩展性，2026-06-14）
> 对 ~940 行自研 Python 做了一次代码评估后，按优先级分 4 个 commit 修补。**全程零改上游**；
> 两个重构（#3/#4）均验证行为不变，故不影响 §9.6–9.11 的结论。

1. **🔴 鲁棒性（Massive collector）**：原 429 是无限 `while: continue`（持续限速会挂死），5xx/超时直接
   `raise_for_status()` 不重试；而上游 `BaseCollector` 在 `joblib.Parallel` 下**无单票 try/except**，
   一次坏响应会拖死/崩溃整批拉取。→ 新增 `_fetch()` 带上限重试（`MAX_RETRIES=6`，退避）覆盖
   429/5xx/网络错误，最终失败则**跳过该票而非崩批**；key 改为只读一次。
2. **🟠 可维护性（测试空白）**：自研面原本零自动化测试。→ `tests/test_fork_collectors.py`（6 个 mock 单测，
   无网络）锁住：symbol 解析、AV 月份分页、Massive OHLC 解析+分页+「重试到上限即跳过」、normalize 的
   `factor/change` 约定。（顺带：`.venv` 装了 `pytest`。）
3. **🟡 架构（脚本重复）**：multiseed/rolling 重复「建数据→按 seed 训练→TopkDropout 回测→算超额」。
   → 抽 `examples/fork/_eval.py`（`load_cfg/build_dataset/train_predict/backtest_excess`），两脚本改用之；
   冒烟精确复现 6 因子 seed0 = +0.2539，**行为零变化**。
4. **🟢 扩展性（因子硬编码）**：因子原是各子类里重复的字符串列表。→ 统一为 `CUSTOM_FACTORS = {名字:(表达式,论据)}`
   注册表，handler 变体只声明 `FACTORS` 名单。加因子=加一行；也是 §10.0「LLM 自动挖因子」的插入点。
   三个 handler 的因子配置逐字不变。

### 9.13 AV 大批量拉取：用单线程节流，别靠并发撞限速（2026-06-14 实测）
- 现象：拉全 S&P500 基本面用 `--max_workers 4`，日志里 80+ 次 `AV throttle`，预计耗时从 ~30 分钟
  膨胀到 **~1 小时 45 分**。
- 原因：AV $49.99 档限速是 **75 请求/分钟（无每日上限）**。并发 4 线程 × 每票 3 个端点，瞬时请求
  超过 75/min → 每次触发，我们的 `_get` 重试逻辑就**罚睡 60 秒**（AV 的 `Note/Information` 软限速）。
  并发不但没加速，反而因为反复撞限速 + 60s 罚睡而**更慢**。
- **正确姿势**：大批量拉 AV 用 **`--max_workers 1` + 每次请求间小延迟**（节流到 ~70/min，卡在上限之下），
  完全避开 60s 罚睡，净速度更快、更稳。Massive 是无限套餐才适合 `--max_workers 16`（§5.3）——
  **两个源的并发策略相反，别套用。**
- 注：这次没中途重启（BaseCollector 默认重头来，会丢已拉进度），让它带着罚睡跑完；数据正确性不受影响。

### 9.14 基本面 PIT 管线打通（Phase 3，2026-06-14）
- 全 S&P500 基本面拉好：489 个有数据的 instrument（其余 ETF/非个股跳过），23.5 万行，
  7 字段（eps/revenue/grossprofit/netincome/equity/assets/shares），覆盖 ~2007Q4–2026Q1。
- `normalize_data` → `dump_pit` 成功，PIT `.bin` 落在 `us_data_massive/financial/<symbol>/`（和价格 `.bin` 并存）。
- **dump_pit 两个坑**：① CLI 参数名是 `--csv_path` / `--freq`（不是 dump_bin 的 `--data_path`/`--interval`），
  且 `dump` 是方法、要放在构造参数**之后**：`dump_pit.py --csv_path .. --qlib_dir .. --freq quarterly dump`。
  ② **季频会给字段名再加 `_q` 后缀**：我们的 `eps_q` → 落盘 `eps_q_q`，故表达式里引用为 **`P($$eps_q_q)`**。
- **PIT 因子表达式**：必须用 `P(...)` 包裹 PIT 引用（`$$`），可与日频 `$close` 混算（P 把季频对齐到日历，
  且只看"截至当日已公告"的值，无前视）。实测：AAPL 2023末 TTM 盈利收益率 3.17%、ROE 0.37，数值正确。
  PIT 不能用裸 `D.features(freq='day')` 查 `$$x`，必须 `P($$x)`。

### 9.15 基本面因子滚动回测：§9.11 假设确认——更稳，非更赚（Phase 3，2026-06-14）
- `Alpha158CustomFund` = Alpha158Custom5（5 价/量）+ 6 个 PIT 价值/质量/成长因子（EY_TTM/BM/ROE/
  GPOA/GMARGIN/SALESGRWTH，§9.14）。同一 walk-forward 设置（2016–2026，每窗重建+3seed 平均）。
- **逐年超额 vs Custom5（§9.11）**：

  | 年 | Custom5 | Fund | | 年 | Custom5 | Fund |
  |---|---|---|---|---|---|---|
  | 2016 | +17.8% | +13.3% | | 2021 | +1.0% | +1.0% |
  | 2017 | −8.5% | −8.2% | | 2022 | +7.8% | +3.1% |
  | **2018** | **−9.1%** | **+0.2%** ✅ | | 2023 | +33.9% | +41.6% |
  | **2019** | **−8.3%** | **+0.4%** ✅ | | 2024 | −9.3% | −9.8% |
  | 2020 | +42.1% | +44.6% | | 2025 | +31.8% | +13.9% |
  |  |  |  | | 2026* | +25.4% | +24.8% |
  | **正年/均值/std** | **7/11 · +11.3% · 19.6pp** | **9/11 · +11.3% · 18.6pp** | | | | |

- **裁决（§9.11 假设确认，但要点在"怎么改善的"）**：
  - ✅ 基本面把 2017–19 三连亏里的 **2018、2019 从 ~-9% 修到持平正**，连亏段消除，正年 7/11 → **9/11**，
    只剩 2017、2024 两个孤立亏年。机制如预期：价值/质量正交于动量，在动量跑输年顶上。
  - ⚠️ **均值不变（都 +11.3%）**：不是"多挣 alpha"，而是**分散化**——削大年上行（2016/2022/2025）换更少更浅的亏年，
    同均值、更一致、尾部更轻（std 19.6→18.6）。**没根治**：2017/2024 仍亏 ~-9%，最差年仍 -10% 量级。
  - 脚本 "robust across regimes" 是 9/11≥0.7 的机械阈值，准确表述应为"明显更一致、连亏段消除"。
- **当前最优改为 `Alpha158CustomFund`**：同均值、更稳、连亏段消除（需 PIT 数据在位）。实盘最怕连亏，一致性提升有真实价值。
  ☐ 续做：gain/SHAP 看是哪几个基本面因子在起作用（value vs quality）；多 seed 复核；削大年上行能否找回。

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
| **3 自定义因子/模型/策略** | 在 `qlib/custom/` 写我们自己的 handler/model/strategy + YAML | ◐ 进行中（2026-06-14） | ☑ 验收达成 + 一轮完整研究闭环（含自我证伪）：自定义因子经 `module_path` 跑通；归因 单因子IC→gain/SHAP；剪枝 IC剪枝(崩)→SHAP剪枝；多 seed 检验证伪单 seed +15%。**沉淀的方法论：因子取舍看 Rank IC+gain/SHAP，业绩对比须多 seed**。☑ 滚动稳健性检验暴露 regime 依赖(2017–19连亏段)。☑ **接入 PIT 基本面并确认 §9.11 假设**：加价值/质量因子把 2018/2019 从 -9% 修到持平、正年 7/11→9/11、同均值(+11.3%)更稳=「更稳非更赚」。默认 `Alpha158CustomFund`（§9.6–9.15）。☐ 续做：基本面因子归因(value vs quality) / 多seed复核 / 美股调参 / 自定义模型 / 自定义策略 |

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
