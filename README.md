# TextConv

![TextConv](assets/logo-256.png)

把复制来的一坨文本，一键变成**能直接粘进代码或表格的格式**。

不用打开窗口、不用选文件、不用点“转换”。复制 → 按一下快捷键 → 结果直接出现在光标处。

支持 **macOS 菜单栏** 和 **Windows 托盘**，两边都有全局快捷键、右键入口和图形设置。

---

## 它到底解决什么问题

真实场景，每天都会遇到：

- 从 Excel、聊天记录、工单系统里复制一列 ID，要拼成 `WHERE id IN ('1001', '1002', ...)`
- 一堆名字要贴回 Excel，但源文本是 `张三、李四、王五`
- 拿到 100 个值，要写成 Python 列表 / JSON 数组塞进脚本
- 中文枚举混着空格、顿号、中英文逗号，手动替换一下午

**以前**：打开转换工具 → 粘贴 → 选格式 → 点转换 → 复制 → 切回去粘贴。六步。
**现在**：复制 → `⌃⌥⌘S`（Windows 是 `Ctrl+Alt+Shift+S`）→ 完事。

转换结果会**写回剪贴板并自动粘贴**，所以你在任何输入框里按下快捷键，结果就落在光标处。

---

## 30 秒上手

### macOS（11 及以上）

1. 下载 `TextConv-*.dmg`，把 `TextConv.app` 拖进「应用程序」
2. **第一次打开必须右键 App →「打开」→ 再点「打开」**（未签名，原因见[排查](#macos-排查)）
3. 系统设置 → 隐私与安全性 → **辅助功能** → 勾选 `TextConv`（自动粘贴需要）
4. 复制一段文本，按 `⌃⌥⌘S`，光标处会出现 SQL IN

装好后**只有菜单栏图标，没有 Dock 图标**，这是故意的。

### Windows（10 / 11）

1. 下载 `TextConv-Setup-*.exe` 双击安装；或下载 `TextConv-Portable-*.exe` 直接双击（免安装、免联网）
2. SmartScreen 拦截时点「更多信息」→「仍要运行」
3. 装完右下角出现托盘图标
4. 复制文本，按 `Ctrl+Alt+Shift+S`

在线安装版需要联网下载 Python 和依赖（约 1 分钟，内置国内镜像）；自包含版全打进去了，不联网也能用。

---

## 六种输出

同一个输入 `苹果 香蕉 橙子`：

| 格式 | 快捷键 macOS / Windows | 输出 |
|---|---|---|
| SQL IN 子句 | `⌃⌥⌘S` / `Ctrl+Alt+Shift+S` | `('苹果', '香蕉', '橙子')` |
| Python 元组 | `⌃⌥⌘P` / `Ctrl+Alt+Shift+P` | `('苹果', '香蕉', '橙子')` |
| Python 列表 | `⌃⌥⌘L` / `Ctrl+Alt+Shift+L` | `['苹果', '香蕉', '橙子']` |
| JSON 数组 | `⌃⌥⌘J` / `Ctrl+Alt+Shift+J` | `["苹果", "香蕉", "橙子"]` |
| Excel 粘贴 | `⌃⌥⌘E` / `Ctrl+Alt+Shift+E` | 每项一行，粘进 Excel 是一列 |
| Excel 一列 | `⌃⌥⌘K` / `Ctrl+Alt+Shift+K` | 同 Excel 粘贴；多列时只取第一列 |

**分隔符自动识别**：空白、换行、`、`、`,`、`，`、`;`、`；` 都会切开，不用先手动替换。

---

## 多列文本 = 表格模式

如果粘贴的内容里有 **Tab**（从 Excel / 表格里复制就会带），TextConv 会按“一行一条记录”处理，而不是把所有内容揉成一条。

输入（制表符分隔，最后一行和第一行重复）：

```
苹果	3
香蕉	5
苹果	3
```

| 格式 | 输出 |
|---|---|
| SQL IN | `('苹果', '3'),\n('香蕉', '5')` |
| JSON | `[["苹果", "3"], ["香蕉", "5"]]` |
| Python 元组 | `(('苹果', '3'), ('香蕉', '5'))` |
| Python 列表 | `[['苹果', '3'], ['香蕉', '5']]` |
| Excel 粘贴 | 原样保留表格（Tab 分隔），直接贴回 Excel |
| Excel 一列 | `苹果\n香蕉`（只取第一列） |

注意两点：

- **按行去重**：重复的整行会被去掉（`苹果 3` 出现两次只保留一次），顺序不变。可在设置里关掉。
- 只有一行但带 Tab，也算一条记录，输出是 `[['a', 'b']]` 这种“一行两列”。

纯单列 / 单行文本（没有 Tab）走普通模式，行为和以前完全一致，不会多包一层括号。

---

## 怎么触发（两个平台不一样，别混）

### macOS：三种入口

| 入口 | 怎么用 | 说明 |
|---|---|---|
| 全局快捷键 | `⌃⌥⌘S/E/J/P/L/K` | 任何 App 里都能用，读剪贴板 → 转换 → 自动粘贴 |
| 菜单栏图标 | 点图标 → 选格式 | 菜单里也会显示当前快捷键 |
| 右键「服务」 | 选中文字 → 右键 → 服务 → `TextConv · SQL IN 子句` | 直接替换选中的文字，不用先复制 |

快捷键前缀是 `⌃` Control + `⌥` Option + `⌘` Command，六个格式对应 S/E/J/P/L/K（SQL / Excel / JSON / Python 元组 / List / 列）。

### Windows：三种入口

| 入口 | 怎么用 | 说明 |
|---|---|---|
| 全局快捷键 | `Ctrl+Alt+Shift+S/E/J/P/L/K` | 同上：读剪贴板 → 转换 → 自动粘贴 |
| 托盘图标 | 右键托盘 → 选格式 | 还有分隔符开关、去重、自动粘贴、提示音、设置 |
| 资源管理器右键 | 右键**文件** → `TextConv 转换` → 复制为 … | 转换**文件内容**，不是选中的文字 |

> Windows 的右键菜单是挂在“文件”上的（注册表 `*\shell\TextConv`），和 macOS 的“服务”语义不同：
> macOS 处理的是**选中的文字**，Windows 处理的是**文件内容**。
> Windows 想处理剪贴板文字直接用快捷键（或 `tc` 命令）。

### 命令行（不是所有安装方式都有）

`tc` 命令只有**从源码安装**（macOS）和 **Windows 在线安装版** 才有：
Windows 会把 `.venv\Scripts` 加进用户 PATH；macOS 在项目目录里用 `.venv/bin/tc`。
dmg 版和 Portable 版只提供图形界面，没有命令行。

```bash
tc --formats                         # 列出所有格式
echo "苹果 香蕉 橙子" | tc sql        # 从管道读，结果打到屏幕
tc json --input clipboard --copy     # 剪贴板内容转 JSON 并写回剪贴板
tc --doctor                          # 体检：权限、快捷键、服务、版本
```

macOS 源码安装时把 `tc` 换成 `.venv/bin/tc`，或者先 `source .venv/bin/activate`。

---

## 设置

| 平台 | 打开方式 | 配置文件 |
|---|---|---|
| macOS | 菜单栏图标 →「设置…」 | `~/Library/Application Support/TextConv/config.json` |
| Windows | 右键托盘 →「设置…」 | `%APPDATA%\TextConv\config.json` |

能改的东西：

- **分隔符**：勾选内置的 7 种（空白/换行、顿号、中英文逗号、中英文分号），还能加自定义分隔符（比如 `|`）
- **快捷键**：六个格式各自绑定，冲突了自己换
- **去重**：默认开，保持顺序
- **自动粘贴**：默认开；关掉就只写剪贴板
- **提示音**：默认关

改完立即生效，不用重启（快捷键改完会重新注册）。

---

## 安装问题排查

### macOS 排查

**1. 提示“无法打开 TextConv，因为无法验证开发者”**

安装包没有 Apple 开发者签名（$99/年），被 Gatekeeper 拦了。任选一种：

```bash
# 方式一：图形界面
右键 TextConv.app → 打开 → 再点“打开”

# 方式二：命令行去掉隔离属性
xattr -dr com.apple.quarantine /Applications/TextConv.app
```

**2. 按了快捷键，剪贴板变了，但没有自动粘贴**

辅助功能权限没给。系统设置 → 隐私与安全性 → **辅助功能** → 点 `+` → 选 `/Applications/TextConv.app`。

如果你是用终端 `./run.sh` 启动的，权限会继承终端本身，通常不需要单独授权。

**3. 右键「服务」里找不到 TextConv · …**

服务菜单缓存偶尔不刷新：

- 注销重新登录一次（最有效）
- 或打开一次「自动操作（Automator）」，随便新建一个工作流再关掉，触发缓存刷新
- 确认文件确实生成了：`ls ~/Library/Services | grep TextConv`

**4. 快捷键按了没反应**

- 菜单栏图标还在吗？App 没运行就没有快捷键
- 和别的 App 冲突了？菜单栏 →「设置…」→ 换一组
- 系统设置 → 隐私与安全性 → 辅助功能，把 TextConv 删掉再重新加一次

**5. 菜单栏图标不见了**

菜单栏太满被挤到屏幕外，或用了 Bartender 之类的收纳工具。退出几个别的 App，或用 `tc --doctor` 确认进程还在。

**6. 怎么彻底卸载**

```bash
# 1. 先退出（菜单栏 → 退出 TextConv）
# 2. 删 App
rm -rf /Applications/TextConv.app
# 3. 删右键服务
rm -rf ~/Library/Services/TextConv*
# 4. 如果有开机自启
launchctl bootout "gui/$(id -u)/com.local.textconv.menubar" 2>/dev/null
rm -f ~/Library/LaunchAgents/com.local.textconv.menubar.plist
# 5. 删配置（可选）
rm -rf "~/Library/Application Support/TextConv"
```

### Windows 排查

**1. SmartScreen 拦截**

点「更多信息」→「仍要运行」。安装包没有购买代码签名证书，属于正常现象。

**2. 杀毒软件报毒**

NSIS / PyInstaller 打包的程序被误报是常态。可以加白名单，或者直接从源码运行（见下方“开发”）。

**3. 在线安装时下载 Python 失败**

- 换用 `TextConv-Portable`（自包含，不需要联网）
- 或手动指定镜像：`install.ps1 -Mirror https://pypi.tuna.tsinghua.edu.cn/simple`
- 安装日志在 `%APPDATA%\TextConv\install.log`，里面记录了每个源的回退过程

**4. Win11 右键菜单里没有 TextConv**

Win11 默认折叠了旧版右键菜单：右键 →「显示更多选项」，或按 `Shift + F10`。

**5. 托盘图标找不到**

在任务栏右下角的「^」溢出区里，拖出来固定即可。

**6. 快捷键没反应**

- 托盘进程还在吗（任务管理器里找 `pythonw.exe` 或 `TextConv.exe`）
- 和别的软件冲突：右键托盘 →「设置…」换一组
- 部分以管理员身份运行的窗口收不到普通程序的模拟按键

**7. 怎么卸载**

设置 → 应用 → 已安装的应用 → `TextConv` → 卸载。
或者运行安装目录下的 `uninstall.bat`。

---

## 开发

```bash
git clone https://github.com/kaen-w/textconv.git
cd textconv

# macOS
./install.sh          # 建 venv、装 PyObjC、装 6 个右键服务、生成 TextConv.app
./run.sh              # 前台运行，Ctrl+C 退出

# Windows
install.bat           # 建 venv、装依赖、注册托盘/右键菜单/自启
run.bat               # 启动托盘
debug.bat             # 带控制台启动，方便看报错
```

跑测试（纯标准库逻辑，65 个用例）：

```bash
python -m unittest discover -s tests
```

打包：

```bash
tools/build_macos.sh            # dist/TextConv.app + dist/TextConv-<版本>.dmg
tools/build_windows.sh          # dist/TextConv-Setup-<版本>.exe（NSIS，macOS 上也能编）
tools/build_windows_portable.sh # 自包含 exe（需在 Windows 上跑）
```

---

## 配置项参考

`config.json` 的全部字段：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `delimiters` | 数组 | `["whitespace", "、", ",", "，", ";", "；"]` | 启用的分隔符；`whitespace` 是空白和换行的占位符 |
| `custom_delimiters` | 数组 | `[]` | 自己加的分隔符，例如 `["|", "·"]` |
| `dedupe` | 布尔 | `true` | 去重（表格模式按行去重） |
| `auto_paste` | 布尔 | `true` | 转换后自动模拟粘贴 |
| `play_sound` | 布尔 | `false` | 完成后提示音 |
| `hotkeys` | 对象 | 见上文 | 每个格式的快捷键字符串 |
| `asked_permission` | 布尔 | `false` | 是否已经提示过辅助功能授权 |

---

## 项目结构

```
textconv/
├── textconv/
│   ├── core.py            # 切分、表格识别、六种格式渲染（纯标准库）
│   ├── config.py          # 配置读写、各平台默认键位与路径
│   ├── clipboard.py       # 剪贴板读写（AppKit / Win32）
│   ├── paste.py           # 模拟粘贴（CGEvent / keybd_event）
│   ├── hotkeys.py         # macOS 全局快捷键（Carbon）
│   ├── menubar.py         # macOS 菜单栏 App
│   ├── settings_window.py # macOS 设置窗口（AppKit）
│   ├── services.py        # macOS 右键服务（Automator 工作流）
│   ├── win_tray.py        # Windows 托盘
│   ├── win_hotkeys.py     # Windows 全局快捷键
│   ├── win_settings.py    # Windows 设置窗口（Tk）
│   ├── fileconv.py        # Windows 右键文件转换
│   └── cli.py             # tc 命令行
├── tools/                 # 图标生成、打包脚本
├── assets/                # 图标与菜单栏模板图
└── tests/                 # 单元测试
```

---

## 已知限制

- macOS 包未做苹果签名/公证，首次打开需要手动放行（见排查第 1 条）。
- Windows 安装包未购买代码签名证书，SmartScreen 会提示。
- Windows 右键菜单作用于**文件**，不是选中的文字；处理剪贴板请用快捷键或 `tc`。
- 多列判定只看 **Tab**；用逗号分隔的“两列”会被当成一列里的多个值。

## 许可

[MIT](LICENSE)
