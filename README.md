# TextConv

![TextConv](assets/logo-256.png)

## 下载

| 平台 | 安装包 | 说明 |
|---|---|---|
| Windows 10/11 | [TextConv-Setup.exe](https://github.com/kaen-w/textconv/releases/latest) | 双击安装，自动装依赖并注册托盘 / 右键菜单 |
| macOS 11+ | [TextConv.dmg](https://github.com/kaen-w/textconv/releases/latest) | 拖进「应用程序」，首次启动在系统设置里授予辅助功能权限 |

不用安装也能跑：`pip install -e .` 后 `python -m textconv.menubar`（macOS）或 `python -m textconv.win_tray`（Windows）。


把零散文本（复制来的名单、编号、中文枚举）一键转成 **SQL IN 子句 / Excel 粘贴 / JSON 数组 / Python 元组或列表**，并且直接接进 macOS 的**右键菜单**和**全局快捷键**，不用再打开一个窗口点“转换”。

原来的 `converter_gui.py` 是一个独立窗口：粘贴 → 选格式 → 点转换 → 复制。现在同样的逻辑搬到了系统层：

| 原 GUI 格式 | 现在怎么用 | 输出 |
|---|---|---|
| `sql` | ⌃⌥⌘S / 右键“TextConv · SQL IN 子句” | `('苹果', '香蕉')` |
| `excel` | ⌃⌥⌘E / 右键“Excel 粘贴” | `苹果`↵`香蕉` |
| `json` | ⌃⌥⌘J / 右键“JSON 数组” | `["苹果", "香蕉"]` |
| `python` | ⌃⌥⌘P / 右键“Python 元组” | `('苹果', '香蕉')` |
| 新增 | ⌃⌥⌘L / ⌃⌥⌘K | `['苹果', '香蕉']` / 一列一个值 |

去重默认开启（和原 GUI 一样，保持原顺序），菜单和设置里都能关。

> **Windows 版**：同目录下的 [TextConv-Windows.zip](TextConv-Windows.zip)，解压后双击
> `install.bat`，说明见 [README-Windows.md](README-Windows.md)。
> Windows 用**托盘 + 全局热键**（Ctrl+Alt+Shift+S/E/J/P/L/K）——Windows 同样不允许
> 第三方改别的程序的文本右键菜单，但合成按键不需要任何授权，体验比 macOS 更省事。

---

## 一、装好就能用的三种方式

### 1. 右键（服务 / Services）

选中一段文本 → 右键 → **服务** → `TextConv · SQL IN 子句`

- 转换结果会**直接替换选中的文本**（工作流声明了 `NSReturnTypes`）；
- 同时已经写进剪贴板，所以任何 App 里按 ⌘V 也能用；
- 不需要任何权限，装完即生效。

> macOS 不允许第三方 App 往别的 App 的右键菜单里插条目，**“服务”子菜单是系统唯一开放的口子**，所以条目长这样，不是我们偷懒。

### 2. 全局快捷键（菜单栏 App）

```
复制文本  →  ⌃⌥⌘S  →  光标处直接出现 SQL IN 子句
```

先双击 `/Applications/TextConv.app` 启动（或 `./install.sh --autostart` 开机自启），之后在**任何 App** 里都能用，包括终端、Excel、浏览器输入框。

| 快捷键 | 动作 |
|---|---|
| ⌃⌥⌘S | SQL IN 子句 |
| ⌃⌥⌘E | Excel 粘贴（原样，一个值一行；多列保留表格） |
| ⌃⌥⌘J | JSON 数组 |
| ⌃⌥⌘P | Python 元组 |
| ⌃⌥⌘L | Python 列表 |
| ⌃⌥⌘K | Excel 一列（换行分隔） |

**快捷键本身不需要任何权限**（Carbon 全局热键，系统层面截获，不会漏给当前 App）。

“转换后自动粘贴”才需要**辅助功能权限**：没授权时结果只进剪贴板，自己按 ⌘V。
授权入口在菜单里：**授予“自动粘贴”权限…**，然后在“系统设置 → 隐私与安全性 →
辅助功能”里勾选 `.venv/bin/python`（真实路径是 `/opt/anaconda3/bin/python3.12`）。
从终端直接 `./run.sh` 启动时，权限会继承终端，通常不用单独授权。

> 为什么要“激活一次”？实测 macOS 26 下，**从未成为过前台 App 的后台程序收不到
> Carbon 热键事件**。所以 App 启动时会激活自己 0.25 秒再把前台还给原来的 App，
> 之后退到后台也能正常接收热键。属于内部细节，你无感。

### 3. 命令行

```bash
.venv/bin/tc sql --input clipboard --copy   # 剪贴板内容 → SQL IN → 写回剪贴板
pbpaste | .venv/bin/tc json                 # 管道输入 → 标准输出
.venv/bin/tc column --delim "、" --no-dedupe # 自定义分隔符、关闭去重
.venv/bin/tc --formats                      # 看所有格式
.venv/bin/tc --doctor                       # 诊断：权限 / 服务 / 进程 / 快捷键
```

`install.sh` 会把 `tc` 装到 `.venv/bin/tc`；想在任何地方直接敲 `tc`，加个软链接：

```bash
ln -sf "$PWD/.venv/bin/tc" ~/.local/bin/tc   # 确保 ~/.local/bin 在 PATH 里
```

---

## 二、分隔符自定义

默认就会按这些切分：**空白 / 换行 / 制表符、顿号 `、`、逗号 `,`、全角逗号 `，`、分号 `;`、全角分号 `；`**。

想改的话有三个入口：

1. **菜单栏图标 → 分隔符**：勾选/取消，立即生效，同时写进配置；
2. **菜单栏图标 → 设置…**：还能加**自定义分隔符**（空格分隔，支持多字符如 `::`），以及改快捷键；
3. 直接编辑 `~/Library/Application Support/TextConv/config.json`。

```json
{
  "delimiters": ["whitespace", "、", ",", ";", "，", "；"],
  "custom_delimiters": ["|", "::"],
  "dedupe": true,
  "auto_paste": true,
  "play_sound": true,
  "hotkeys": { "sql": "ctrl+alt+cmd+s" }
}
```

> 小提示：如果某条数据本身带空格（比如 `New York`），又不想被空格拆开，就去设置里取消勾选“空白”，只留 `、` 之类的分隔符。

---


## 它会不会动我的剪贴板？

会，这是“自动粘贴”的实现方式（不是逐字模拟输入，而是把结果放进剪贴板再触发一次 ⌘V）：

| 你按的 | 行为 |
|---|---|
| `⌘V` | 系统原生粘贴，剪贴板里是什么就贴什么，本工具不拦截 |
| `⌃⌥⌘S` 等 | 读剪贴板 → 转换 → **用结果替换剪贴板** → 自动按 ⌘V |

所以按完快捷键，剪贴板里是**转换结果**；想粘原文就重新复制一次。
连续按同一个快捷键不会叠加转义：程序记住了上一次的原始输入，剪贴板里正好是上次结果时会从原文重转。

**剪贴板里不是纯文本时：**

| 你复制的 | 按快捷键会怎样 |
|---|---|
| 图片、文件、文件夹 | 拿不到纯文本 → **什么都不做**，状态栏提示“剪贴板为空”，**剪贴板原样不动** |
| 富文本 / 网页内容 | 自动取其中的纯文本部分，正常转换（格式会丢，输出是代码，本来就只要文本） |
| Excel 单元格 | 本来就是制表符/换行分隔的纯文本，正常转换 |
| 只有 RTF、没有纯文本的极少数 App | 会被当成空。先在目标 App 里用「粘贴为纯文本」再复制一次 |


## 从 Excel 复制多列会怎样？

只要剪贴板里出现 **Tab**，就进入“表格模式”：**一行是一条记录**，去重按整行。
没有 Tab 的普通文本完全不受影响，还是按分隔符切。

例：复制 2 列 3 行（前两行完全相同）

```
PG2203-M-FBA    B08QRTTK6W
PG2203-M-FBA    B08QRTTK6W
B1              X9
```

| 格式 | 结果（去重开） |
|---|---|
| SQL IN | `('PG2203-M-FBA', 'B08QRTTK6W'),`<br>`('B1', 'X9')` —— 行元组，可直接接在 `VALUES` 后面 |
| JSON | `[["PG2203-M-FBA", "B08QRTTK6W"], ["B1", "X9"]]` —— 数组的数组 |
| Python 元组 / 列表 | `(('...', '...'), ('...', '...'))` / `[['...', '...'], ...]` |
| Excel 粘贴 | 保持粘贴原样（Tab 分列、换行分行），重复行去掉 |
| Excel 一列 | 只取第一列（想要别的列，直接在 Excel 里复制那一列即可） |

## 关于图标

![logo](assets/logo-256.png)

图标就是这款工具的输出：**`('a')`**。

- 括号 = `IN (...)` / 元组的边界
- 单引号 = 字符串字面量
- 琥珀金 = 值本身

看得懂 SQL 的人一眼就知道它是干什么的，不需要额外解释。底色深墨蓝，只用两种前景色，没有渐变和阴影——缩小后不会糊成一团。

16/24px 会自动退化成 `'a'`（`assets/logo-16.png`）：三四个字符塞进 16px 只剩噪点，两个引号加一个字母至少还认得出。

源文件由脚本生成，改字/改色改 `tools/make_logo.py` 顶部的常量后重跑：

```bash
python tools/make_logo.py     # 输出 PNG / ICO / ICNS / SVG 到 assets/
```

| 文件 | 用途 |
|---|---|
| `assets/logo.svg` | 矢量源 |
| `assets/textconv.ico` | Windows 托盘 + 右键菜单 + 应用图标（16/24 简化版，32+ 完整版） |
| `assets/TextConv.icns` | macOS 应用图标 |
| `assets/logo-tray.png` | Windows 托盘用（简化版 32px） |
| `assets/logo-*.png` | 文档与分享用 |

## 打包发布

```bash
# macOS：生成 dist/TextConv.app 和 dist/TextConv-<version>.dmg
tools/build_macos.sh

# Windows：生成安装包（需要 NSIS）
tools/build_windows.sh
```

打 tag 后推送到 GitHub，CI 会自动构建两个安装包并挂到 Release 上：

```bash
git tag v0.2.6 && git push origin v0.2.6
```

## 三、安装

```bash
cd /Users/kaen/pythonProject/goodidea/textconv
./install.sh              # 建虚拟环境 + 装 PyObjC + 6 个右键服务 + 生成 TextConv.app
./run.sh                  # 前台运行（调试用，Ctrl+C 退出）
./install.sh --autostart  # 想要开机自启 + 立即在后台启动
./install.sh --uninstall  # 卸载服务与自启
```

装完如果右键“服务”里没看到：注销重新登录一次，或打开一次“自动操作”随便存个快捷操作刷新缓存（`pbs` 偶尔要踢一脚）。

---

## 四、目录结构

```
textconv/
├── textconv/
│   ├── core.py            # 切分 + 各格式渲染（纯标准库，27 个单测覆盖）
│   ├── config.py          # 配置读写（~/Library/Application Support/TextConv）
│   ├── clipboard.py       # NSPasteboard 读写，退化为 pbpaste/pbcopy
│   ├── paste.py           # ⌘V 模拟 + 辅助功能权限
│   ├── hotkeys.py         # Carbon RegisterEventHotKey（ctypes，无需输入监控权限）
│   ├── menubar.py         # 菜单栏 App：状态项、菜单、快捷键分发
│   ├── settings_window.py # 原生设置窗口
│   ├── services.py        # 生成 / 卸载 Automator 服务工作流
│   └── cli.py             # tc 命令
├── tests/                 # 27 个核心 + 9 个 GUI 测试
├── install.sh / run.sh
└── pyproject.toml
```

### 开发

```bash
.venv/bin/python -m unittest discover -s tests -v   # 全量测试
.venv/bin/python -m textconv.menubar --self-test    # 菜单栏/快捷键/设置窗口自检
.venv/bin/python -m textconv.services status        # 看服务装了几个
```

---

## 五、常见问题

**快捷键没反应？**
先跑一次自检：

```bash
.venv/bin/python -m textconv.cli --doctor
```

它会告诉你菜单栏 App 在不在跑、快捷键注册有没有失败、权限够不够、服务装了几个。
菜单栏是一个单色模板图标（当前样式：**折角文档 + TS**，跟随系统明暗自动变色）；`assets/menubar.png` 缺失时会自动退回文字 TC。

想换样式可以跑 `./switch-icon.sh tile_ts|clipboard|document|document_ts|bubble`，脚本会重生成图标并重启菜单栏 App。

**按了快捷键只复制没粘贴？**
没有辅助功能权限（`--doctor` 里会显示“✗ 未授权，只复制不粘贴”）。
菜单 →“授予‘自动粘贴’权限…”，然后在“系统设置 → 隐私与安全性 → 辅助功能”里
把 `.venv/bin/python` 勾上即可，**不用重启 App**，下一次按键就生效。

**右键转换后没替换选中文本？**
某些 App（比如部分 Electron 应用）不吃服务的返回文本。结果已经在剪贴板里，⌘V 即可。

**开机自启后想关掉？**
`./install.sh --uninstall`（会一并删掉 `/Applications/TextConv.app` 与 LaunchAgent）。

**改完配置要让 App 重读？**
菜单里的开关和设置窗口都会即时生效并落盘；手改 `config.json` 后，重启一次菜单栏 App。
