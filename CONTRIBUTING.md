# 贡献与发版

## 日常改动

- 直接提交到 `main`，一个提交只做一件事，说明写清“改了什么、为什么”
- **不要顺手改版本号**：`textconv/__init__.py`、`pyproject.toml`、`install.ps1` 里的版本只在发版时更新
- 改完跑测试：`python -m unittest discover -s tests`
- 改动涉及行为时，同步更新 `README.md`

## 发版（维护者说“发版”时才做）

1. 确认 `main` 上的改动都验证过，测试全绿
2. 同步版本号（三处）：
   - `textconv/__init__.py` → `__version__`
   - `pyproject.toml` → `version`
   - `install.ps1` → `$version`（注意文件要保留 UTF-8 BOM）
3. 构建产物：
   ```bash
   tools/build_macos.sh          # dist/TextConv-<版本>.dmg
   tools/build_windows.sh        # dist/TextConv-Setup-<版本>.exe
   ```
   > Setup 必须在 macOS 上编译：`installer.nsi` 带 BOM，Windows 上编译才不乱码；
   > `tools/build_windows.sh` 在 macOS 和 Windows 上都能跑。
4. 提交并发 tag：
   ```bash
   git commit -am "chore: release v<版本>"
   git tag v<版本> && git push origin main && git push origin v<版本>
   ```
5. 建 Release 并上传 dmg / Setup：
   ```bash
   gh release create v<版本> dist/*.dmg dist/TextConv-Setup-<版本>.exe \
     --title "TextConv <版本>" --notes-file 说明.md
   ```
6. 触发 CI 构建自包含版并附加到 Release：
   ```bash
   gh workflow run build-installers -f tag=v<版本> -f attach=true
   ```

## 版本策略

- **历史版本保留**，不主动删除；只有确认某个版本的产物是坏的，才删除并在新的 Release 说明里写清楚
- 出过的事故：0.2.14–0.2.16 的 dmg 因为构建时排除了 `hashlib/ssl` 而启动崩溃，已删除

## 检查清单

发版前过一遍：

- [ ] `python -m unittest discover -s tests` 全过
- [ ] `TextConv --check-update`（打包版）能连上 GitHub
- [ ] dmg 挂载后 App 能启动、菜单栏图标正常
- [ ] README 的版本相关描述没有过期
