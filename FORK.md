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
> **最后更新**：2026-06-14

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
# 仓库根目录（包名 pyqlib，import qlib；Python 3.8–3.12）
pip install -e .             # 或 make dev（装齐 dev/lint/docs/test 等 extras）
make prerequisites           # 编译 Cython 扩展（首次必跑）
./scripts/setup-hooks.sh     # 启用 commit 门禁（见 §3.3），每个 clone 一次
```

> Lint/格式沿用上游：black（120 列）+ pylint + flake8 + mypy；`make lint` 一把跑。
> 测试：`cd tests && pytest . -m "not slow"`（见 §7）。

### 5.2 拉数据 + 跑一个 benchmark（先验证环境通）
```bash
# 美股日线示例数据（上游提供）
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/us_data --region us
# 跑一个最小 benchmark
qrun examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml
```
qlib 通过 `qlib.init(provider_uri=..., region="us")` 指向数据目录；美股 region 已内建（`REG_US`）。

### 5.3 接我们的数据源（Alpha Vantage / Massive-Polygon）
qlib 数据是**文件式 `.bin`**，外部数据走"collector → CSV → dump_bin"两步（**不改上游**）：
1. 新建 `scripts/data_collector/<vendor>/collector.py`，仿 `scripts/data_collector/yahoo/`
   的 `BaseCollector` 子类，把 AV/Polygon 行情拉成 CSV（列：symbol,date,open,high,low,close,volume）。
2. `python scripts/dump_bin.py dump_all --csv_dir <csv> --qlib_dir ~/.qlib/qlib_data/us_data --freq day`
   生成 `calendars/` `instruments/` `features/<sym>/<field>.day.bin`。
3. `qlib.init(provider_uri="~/.qlib/qlib_data/us_data", region="us")` 即可用。

> 截至 2026-06-14，上游**没有** Alpha Vantage / Polygon 集成（grep 确认）——这是我们要补的第一块。

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

> （暂空——首次端到端跑通后回填：数据源坑、显存/上下文坑、region 配置坑等。）

---

## 10. 路线图

> **这是跨 session 的持久路线图**——每个 session 进来先看「状态」表，知道做到哪、接着做什么。
> 状态图例：☐ 未开始 ／ ◐ 进行中 ／ ☑ 完成

| Phase | 内容 | 状态 | 验收标准 |
|---|---|---|---|
| **0 脚手架** | FORK.md / CLAUDE.md / commit 门禁 / `qlib/custom/` 空包 | ☑ 完成 | 文档就位；`./scripts/setup-hooks.sh` 生效 |
| **1 跑通环境** | 装好 + 拉美股示例数据 + 跑一个 benchmark | ☐ 未开始 | `qrun` 出回测结果；`pytest -m "not slow"` 基本绿 |
| **2 接自有数据** | AV / Polygon collector → dump_bin → 美股自有数据集 | ☐ 未开始 | `scripts/data_collector/<vendor>/` 产出 CSV 并 dump 成 `.bin`，qlib 能读 |
| **3 自定义因子/模型/策略** | 在 `qlib/custom/` 写我们自己的 handler/model/strategy + YAML | ☐ 未开始 | 自定义类经 `module_path` 跑通一条完整 workflow |

### 设计要求 / 约束
- **不改上游**：定制全部经 `qlib/custom/` + YAML `module_path` + `scripts/data_collector/<vendor>/`。
- **美股优先**：`region="us"`；数据用我们订阅的 AV / Polygon，而非默认 yfinance。
- **定性**：量化策略业绩声称水分大、非确定性；回测≠实盘，任何决策当假设而非策略。
