# TextConv for Windows

把复制来的零散文本（名单、编号、中文枚举）一键转成 **SQL IN / Excel 粘贴 / JSON 数组 /
Python 元组或列表**，并直接粘贴到光标处。

Windows 版有三条路：

1. **全局快捷键**（主力）：复制 → `Ctrl+Alt+Shift+S` → 光标处直接出现结果
2. **文件右键**：任意文件 → `TextConv 转换` → `复制为 SQL IN` 等
3. **托盘菜单**：右键托盘图标

> Windows 不允许第三方往别的程序的**文本编辑框**右键菜单里加条目，这一点和 macOS 一样。
> 所以文本场景走全局热键，文件场景走资源管理器右键。

---

## 一、一键安装

1. 解压整个文件夹（路径别太深，别放 `Program Files` 下）
2. 双击 **`install.bat`**
3. 装完会自动启动托盘，右下角出现 TextConv 图标（深色圆角 + 金色 `'a'`）

**不需要管理员权限**：所有写入都是“当前用户”范围（`HKCU` 注册表 + 用户 PATH + 本地 `.venv`）。

`install.bat` 会自动做这些事：

| 步骤 | 说明 |
|---|---|
| 找 Python | 依次找 `python` / `py -3` / 常见安装目录，要求 ≥ 3.9 |
| 没 Python 就装 | 先试 `winget`，不行就下载官方安装包：**华为云 → npmmirror → python.org**，静默装（仅当前用户） |
| 建虚拟环境 | `.venv` |
| 装依赖 | PyPI 源依次回退：**清华 → 阿里 → 官方**，全失败才报错 |
| 生成图标 | `assets\textconv.ico` |
| 写环境变量 | 把 `.venv\Scripts` 加进**用户 PATH**（新终端里可直接敲 `tc`） |
| 注册开机自启 | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| 注册右键菜单 | `HKCU\Software\Classes\*\shell\TextConv`（任意文件，级联子菜单） |
| 注册卸载项 | 设置 → 应用 里出现 TextConv |
| 自检 + 启动 | 六项检查 → 启动托盘 |

装完如果自检有 `FAIL`，把它贴给我。

> 国内网络：脚本默认就会走国内镜像。要指定别的源：
> `install.bat -Mirror https://pypi.tuna.tsinghua.edu.cn/simple`

---

## 二、怎么用

### 快捷键（主力）

| 快捷键 | 结果 | 例：`苹果、香蕉、橘子` |
|---|---|---|
| `Ctrl+Alt+Shift+S` | SQL IN 子句 | `('苹果', '香蕉', '橘子')` |
| `Ctrl+Alt+Shift+E` | Excel 粘贴 | `苹果`↵`香蕉`↵`橘子`（一值一行） |
| `Ctrl+Alt+Shift+J` | JSON 数组 | `["苹果", "香蕉", "橘子"]` |
| `Ctrl+Alt+Shift+P` | Python 元组 | `('苹果', '香蕉', '橘子')` |
| `Ctrl+Alt+Shift+L` | Python 列表 | `['苹果', '香蕉', '橘子']` |
| `Ctrl+Alt+Shift+K` | Excel 一列 | 一个值一行 |

**自动粘贴**默认开启：按完热键，结果直接出现在光标处。不想要就托盘右键 →
取消“转换后自动粘贴”，那就只复制，自己按 Ctrl+V。

### 右键文件

在资源管理器里右键任意文件 → **TextConv 转换** → 选一种格式：

> Windows 11 把第三方菜单折叠进了二级菜单：右键后点 **“显示更多选项”**（或按 Shift+F10）
> 才能看到 `TextConv 转换`。这是 Windows 11 的限制，除非做一个签名的 COM 扩展，
> 而那种东西要证书、还要被 SmartScreen 盯着，不适合这种小工具。日常用热键更顺。

- 读取文件内容（自动识别 UTF-8 / GBK / UTF-16）
- 按**和快捷键同一套分隔符**切分，转换后复制到剪贴板，右下角浮出“✓ 已复制 SQL IN 子句”
- 适合**一行一个**的 ID 列表 / 导出清单

**两个边界要知道：**

| 文件 | 结果 |
|---|---|
| 一行一个 ID（最常见） | ✅ `('A001', 'A002', 'A003')` |
| 顿号/分号分隔的单行列表 | ✅ 按分隔符切开 |
| **CSV（`id,name`）** | ⚠️ 逗号也是分隔符，会被切成 `('id', 'name', '1', '张三', ...)`。要按列取值请用 Excel；或临时取消勾选“逗号”再转换 |
| 图片、exe、压缩包等二进制 | 🚫 直接拒绝，提示“跳过：看起来不是文本文件”，**剪贴板不动** |
| 超过 8 MB | 🚫 拒绝，避免卡死 |

### 托盘菜单

右键托盘图标：6 个转换、分隔符勾选、去重/自动粘贴/提示音、设置、退出。

### 命令行

```bat
tc sql --input clipboard --copy
echo 苹果、香蕉 | tc json
tc --formats
tc --doctor
```

（`tc` 在**新开的**终端里才生效；老窗口需要重开。）

---


## 它会不会动我的剪贴板？

会，这是“自动粘贴”的实现方式（不是逐字模拟输入，而是把结果放进剪贴板再触发一次 Ctrl+V）：

| 你按的 | 行为 |
|---|---|
| `Ctrl+V` | 系统原生粘贴，剪贴板里是什么就贴什么，本工具不拦截 |
| `Ctrl+Alt+Shift+S` 等 | 读剪贴板 → 转换 → **用结果替换剪贴板** → 自动按 Ctrl+V |

所以按完快捷键，剪贴板里是**转换结果**；想粘原文就重新复制一次。
连续按同一个快捷键不会叠加引号：程序记住上一次的原始输入，剪贴板里正好是上次结果时会从原文重转。

**剪贴板里不是纯文本时：**

| 你复制的 | 按快捷键会怎样 |
|---|---|
| 图片、文件（资源管理器里复制） | 拿不到纯文本 → **什么都不做**，右下角提示“剪贴板是空的”，**剪贴板原样不动** |
| 富文本 / 网页内容 | 自动取其中的纯文本部分，正常转换 |
| Excel 单元格 | 本来就是制表符/换行分隔的纯文本，正常转换 |


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

## 三、分隔符

默认按这些切：**空白 / 换行 / 制表符、顿号 `、`、逗号 `,`、全角逗号 `，`、分号 `;`、全角分号 `；`**。

改法：托盘右键 → 分隔符 / 设置…，或直接编辑 `%APPDATA%\TextConv\config.json`。

> 数据本身带空格（如 `New York`）时，去设置里取消勾选“空白”，只留 `、` 之类。

---

## 四、卸载

两种方式，效果一样：

- **设置 → 应用 → TextConv → 卸载**
- 双击 **`uninstall.bat`**

会清理：托盘进程、Run 开机自启项、右键菜单、卸载项、用户 PATH 里的条目；
再问你要不要删 `.venv`。**目录本身不会自动删**，不需要了就手动删掉整个文件夹。

---

## 五、排错

```bat
.venv\Scripts\python.exe -m textconv.win_tray --self-test
.venv\Scripts\python.exe -m textconv.cli --doctor
```

| 现象 | 处理 |
|---|---|
| 双击 install.bat 一闪而过 | 用 `cmd` 打开这个目录，手工运行 `install.bat`，报错会留在窗口里 |
| 提示找不到 python | 手动装 Python 3.9+（勾选 Add to PATH），或 `install.bat -PythonExe C:\path\python.exe` |
| 依赖下载失败 | 换源：`install.bat -Mirror https://mirrors.aliyun.com/pypi/simple/`；公司代理记得设 `HTTP_PROXY` |
| 热键没反应 | 微信/QQ/截图工具常占同一组合。托盘右键 → 设置… 换一个；`--doctor` 能看到注册失败项 |
| 只复制没粘贴 | 目标窗口是管理员权限运行的（UIPI 限制）。要么以管理员启动 TextConv，要么手动 Ctrl+V |
| 第一次运行被报毒 | `keyboard` 用键盘钩子实现热键，个别杀软会拦。放行即可，或只用托盘/右键 |
| 右键菜单没出现 | 重启资源管理器：任务管理器 → 重启“Windows 资源管理器”，或注销重登 |
| 复制图片/文件后按键没反应 | 正常的：拿不到纯文本就不动剪贴板，只提示一下 |
| 内容被粘贴了两次 | 0.2.1 起：0.4 秒内的重复触发会被忽略；若仍出现，看日志里是否有两个 pid（=开了两个实例），任务管理器结束所有 `pythonw.exe` 再启动 |
| Excel 里贴不出内容 | Excel 会短暂占用剪贴板，0.2.1 起写入会重试并回读校验；失败会明确提示“写入剪贴板失败”而不是静默贴旧内容 |
| 想改开机自启 | `install.bat -NoAutostart` 重装，或删 Run 键里的 TextConv |
| 连按两次会不会多一层引号 | 不会。程序记住上次的原始输入，剪贴板里是上次结果时会从原文重转（0.2.0 起） |

---

## 六、安装参数

```bat
install.bat                  正常安装
install.bat -NoAutostart     不注册开机自启
install.bat -NoContextMenu   不注册右键菜单
install.bat -NoPath          不改 PATH
install.bat -NoStart         装完不启动
install.bat -Quiet           不询问，能自动的都自动
install.bat -Mirror <url>    指定 PyPI 镜像
install.bat -PythonExe <path> 指定已装的 Python
```

---

## 七、文件清单

```
install.bat          一键安装（调用 install.ps1）
uninstall.bat        一键卸载
install.ps1          安装/卸载逻辑（Python 安装、镜像回退、注册表、PATH）
run.bat              只启动托盘
debug.bat            带控制台启动，排错用
requirements-win.txt pystray / Pillow / keyboard / pyperclip
pyproject.toml       tc 命令入口
textconv/            程序本体
  core.py            切分 + 各格式渲染（与 macOS 版同一套逻辑）
  config.py          配置（%APPDATA%\TextConv\config.json）
  clipboard.py       剪贴板（pyperclip，缺失时走 Win32 API）
  paste.py           模拟 Ctrl+V
  win_hotkeys.py     全局热键
  win_tray.py        托盘程序
  win_settings.py    tkinter 设置窗口
  fileconv.py        右键文件转换（带右下角提示条）
  cli.py             命令行 tc
```
