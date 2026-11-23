"""生成 macOS 右键菜单里的“服务”（Quick Action）工作流。

每个格式生成一个 ``.workflow`` 包，放到 ~/Library/Services，之后在任何 App 里
选中文本 → 右键 → 服务 → “TextConv · SQL IN 子句” 就能就地转换。

工作流的 Shell 脚本只做一件事：把选中的文本交给 ``tc-service`` 处理，脚本把
结果打到 stdout，Automator 再用它替换选中的文本；同时 tc-service 已经把结果
写进剪贴板，所以即使某些 App 不支持替换，也能直接 ⌘V。
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import uuid
from typing import Dict, List, Optional

from .config import app_dir
from .core import FORMATS

SERVICES_DIR = os.path.expanduser("~/Library/Services")
BUNDLE_PREFIX = "TextConv · "  # 和 _service_title 里的分隔符保持一致
RUNNER_NAME = "tc-service"

# 统一的动作元数据，取自系统自带的 Show Map.workflow
_ACTION_TEMPLATE: Dict[str, object] = {
    "AMActionVersion": "2.0.3",
    "AMApplication": ["Automator"],
    "AMParameterProperties": {
        "COMMAND_STRING": {},
        "CheckedForUserDefaultShell": {},
        "inputMethod": {},
        "shell": {},
        "source": {},
    },
    "AMAccepts": {
        "Container": "List",
        "Optional": True,
        "Types": ["com.apple.cocoa.string"],
    },
    "AMProvides": {
        "Container": "List",
        "Types": ["com.apple.cocoa.string"],
    },
    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
    "ActionName": "Run Shell Script",
    "BundleIdentifier": "com.apple.RunShellScript",
    "CFBundleVersion": "2.0.3",
    "CanShowSelectedItemsWhenRun": False,
    "CanShowWhenRun": True,
    "Category": ["AMCategoryUtilities"],
    "Class Name": "RunShellScriptAction",
    "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
    "UnlocalizedApplications": ["Automator"],
    "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/en.lproj/main.nib",
    "isViewVisible": True,
    "location": "300.000000:300.000000",
}


def runner_path() -> str:
    return os.path.join(app_dir(), "bin", RUNNER_NAME)


def _service_title(fmt_label: str) -> str:
    return f"TextConv · {fmt_label}"


def _shell_script(fmt_key: str) -> str:
    # 用 $HOME 拼路径，脚本在 Automator 的 /bin/sh 里也能找到运行器
    return (
        'exec "$HOME/Library/Application Support/TextConv/bin/tc-service" '
        f'"{fmt_key}"'
    )


def _info_plist(fmt_key: str, title: str) -> Dict[str, object]:
    return {
        "CFBundleDevelopmentRegion": "en_US",
        "CFBundleIdentifier": f"com.local.textconv.{fmt_key}",
        "CFBundleName": title,
        "CFBundleShortVersionString": "1.0",
        "NSServices": [
            {
                "NSMenuItem": {"default": title},
                "NSMessage": "runWorkflowAsService",
                "NSSendTypes": ["public.utf8-plain-text"],
                "NSReturnTypes": ["public.utf8-plain-text"],
            }
        ],
    }


def _document_wflow(fmt_key: str, title: str) -> Dict[str, object]:
    action = dict(_ACTION_TEMPLATE)
    action["ActionParameters"] = {
        "COMMAND_STRING": _shell_script(fmt_key),
        "CheckedForUserDefaultShell": True,
        "inputMethod": 0,
        "shell": "/bin/bash",
        "source": "",
    }
    action["arguments"] = {
        "0": {"default value": 0, "name": "inputMethod", "required": "0", "type": "0", "uuid": "0"},
        "1": {"default value": "", "name": "source", "required": "0", "type": "0", "uuid": "1"},
        "2": {"default value": False, "name": "CheckedForUserDefaultShell", "required": "0", "type": "0", "uuid": "2"},
        "3": {"default value": "", "name": "COMMAND_STRING", "required": "0", "type": "0", "uuid": "3"},
        "4": {"default value": "/bin/sh", "name": "shell", "required": "0", "type": "0", "uuid": "4"},
    }
    action["UUID"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"textconv.action.{fmt_key}"))
    action["InputUUID"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"textconv.input.{fmt_key}"))
    action["OutputUUID"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"textconv.output.{fmt_key}"))

    return {
        "AMApplicationBuild": "346",
        "AMApplicationVersion": "2.3",
        "AMDocumentVersion": "2",
        "actions": [{"action": action, "isViewVisible": True}],
        "connectors": {},
        "workflowMetaData": {
            "serviceInputTypeIdentifier": "com.apple.Automator.text",
            "serviceOutputTypeIdentifier": "com.apple.Automator.text",
            "serviceProcessesInput": 1,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


def _write_plist(path: str, data: Dict[str, object]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        plistlib.dump(data, fh, sort_keys=True)


def write_runner(python_executable: str, project_root: str, target: Optional[str] = None) -> str:
    """生成 tc-service 启动脚本，把解释器和项目路径写死，服务无需关心 PATH。"""
    target = target or runner_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if getattr(sys, "frozen", False):
        content = f"""#!/bin/sh
# 由 TextConv 生成，请勿手改；重新运行安装即可覆盖。
exec "{python_executable}" --service --input stdin --output stdout "$@"
"""
    else:
        content = f"""#!/bin/sh
# 由 TextConv 安装脚本生成，请勿手改；重新运行安装即可覆盖。
export PYTHONPATH="{project_root}${{PYTHONPATH:+:$PYTHONPATH}}"
exec "{python_executable}" -m textconv.cli --service --input stdin --output stdout "$@"
"""
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.chmod(target, 0o755)
    return target


def install(
    services_dir: str = SERVICES_DIR,
    python_executable: Optional[str] = None,
    project_root: Optional[str] = None,
    quiet: bool = False,
) -> List[str]:
    """安装运行器 + 全部服务，返回生成的 bundle 路径。"""
    python_executable = python_executable or sys.executable
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    write_runner(python_executable, project_root)

    os.makedirs(services_dir, exist_ok=True)

    # 先清掉旧版本留下的、已经改名的服务（例如 "Excel 筛选" -> "Excel 粘贴"）
    wanted = {f"{_service_title(fmt.label)}.workflow" for fmt in FORMATS}
    try:
        for entry in os.listdir(services_dir):
            if not entry.startswith(BUNDLE_PREFIX) or not entry.endswith(".workflow"):
                continue
            if entry in wanted:
                continue
            shutil.rmtree(os.path.join(services_dir, entry), ignore_errors=True)
            if not quiet:
                print(f"  - 已移除旧服务 {entry}")
    except OSError:
        pass

    created: List[str] = []
    for fmt in FORMATS:
        title = _service_title(fmt.label)
        bundle = os.path.join(services_dir, f"{title}.workflow")
        contents = os.path.join(bundle, "Contents")
        _write_plist(os.path.join(contents, "Info.plist"), _info_plist(fmt.key, title))
        _write_plist(
            os.path.join(contents, "Resources", "document.wflow"),
            _document_wflow(fmt.key, title),
        )
        created.append(bundle)
        if not quiet:
            print(f"  ✓ {title}")
    _refresh_services()
    return created


def uninstall(services_dir: str = SERVICES_DIR, quiet: bool = False) -> List[str]:
    removed: List[str] = []
    for fmt in FORMATS:
        bundle = os.path.join(services_dir, f"{_service_title(fmt.label)}.workflow")
        if os.path.isdir(bundle):
            shutil.rmtree(bundle)
            removed.append(bundle)
            if not quiet:
                print(f"  ✓ 已删除 {os.path.basename(bundle)}")
    _refresh_services()
    return removed


def _refresh_services() -> None:
    """让系统立刻重新扫描服务目录。"""
    for cmd in (
        ["/System/Library/CoreServices/pbs", "-update"],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=15)
        except Exception:
            pass


def installed(services_dir: str = SERVICES_DIR) -> List[str]:
    found = []
    for fmt in FORMATS:
        bundle = os.path.join(services_dir, f"{_service_title(fmt.label)}.workflow")
        if os.path.isdir(bundle):
            found.append(bundle)
    return found


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m textconv.services")
    parser.add_argument("action", choices=("install", "uninstall", "status"))
    parser.add_argument("--services-dir", default=SERVICES_DIR)
    parser.add_argument("--python", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)

    if args.action == "install":
        print("安装右键服务：")
        install(args.services_dir, args.python, args.root)
        print(f"\n完成，共 {len(FORMATS)} 个。")
        print("如果右键菜单里还没出现：注销再登录，或打开“自动操作”随便保存一次。")
        return 0
    if args.action == "uninstall":
        uninstall(args.services_dir)
        return 0
    found = installed(args.services_dir)
    print(f"已安装 {len(found)}/{len(FORMATS)} 个服务")
    for path in found:
        print(f"  {os.path.basename(path)}")
    print(f"运行器：{runner_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
