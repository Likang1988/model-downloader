#!/usr/bin/env python3
"""
一键打包脚本 — 自动检测操作系统平台，打包对应平台的 APP。

Usage:
    python build.py                    # 自动检测当前平台并打包
    python build.py --platform windows # 强制打包 Windows 版本
    python build.py --no-clean         # 跳过清理旧构建
    python build.py --onefile          # 打包为单个文件（默认是目录模式）
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse

# ============================================================
# 项目配置（根据实际情况修改）
# ============================================================
APP_NAME = "ModelDownloader"
MAIN_SCRIPT = "main.py"

# 需要随程序一起分发的目录：(源代码目录, 目标目录)
DATA_DIRS = [
    ("src/icon", "src/icon"),
]

# 需要随程序一起分发的文件：(源文件, 目标目录)
DATA_FILES = []

# 输出目录：用户目录下的 builds 文件夹
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "builds")

# PyInstaller 可能无法自动发现的隐式导入
HIDDEN_IMPORTS = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "qfluentwidgets",
    "requests",
    "tqdm",
    "urllib3",
]

# 明确排除的模块（减小打包体积）
EXCLUDES = [
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "torch",
    "tensorflow",
    "PIL",
    "cv2",
    "notebook",
    "ipython",
]


# ============================================================
# 工具函数
# ============================================================

def get_os_info():
    """获取操作系统平台和架构信息。"""
    system = platform.system().lower()
    arch = platform.machine().lower()

    # 统一架构命名
    if arch in ("amd64", "x86_64"):
        arch = "x86_64"
    elif arch in ("arm64", "aarch64"):
        arch = "arm64"

    return system, arch


def check_pyinstaller():
    """检查 PyInstaller 是否已安装，未安装则自动安装。"""
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True,
            check=True,
        )
        print("[✓] PyInstaller 已安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[*] 正在安装 PyInstaller...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )
        print("[✓] PyInstaller 安装完成")


def clean_build():
    """清理之前的构建产物。"""
    dirs_to_clean = ["build", OUTPUT_DIR]

    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"  删除 {d}/...")
            shutil.rmtree(d)

    # 清理 PyInstaller 临时目录
    pyi_build = os.path.join(OUTPUT_DIR, "build")
    if os.path.exists(pyi_build):
        print(f"  删除 {pyi_build}/...")
        shutil.rmtree(pyi_build)

    # 清理所有 __pycache__
    for root, dirs, _ in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                path = os.path.join(root, d)
                shutil.rmtree(path)

    # 清理 .spec 文件（忽略 build.py 本身）
    for f in os.listdir("."):
        if f.endswith(".spec") and f != os.path.basename(__file__):
            os.remove(f)

    print("[✓] 清理完成")


def get_platform_separator():
    """获取当前平台的 --add-data 分隔符。"""
    return ";" if os.name == "nt" else ":"


# ============================================================
# 构建函数
# ============================================================

def build_app(system, arch, onefile):
    """根据目标平台打包应用。"""
    sep = get_platform_separator()
    icon_path = "src/icon/icon.ico"

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 基础命令
    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        f"--name={APP_NAME}",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={os.path.join(OUTPUT_DIR, 'build')}",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 隐藏控制台窗口（GUI 应用）
    cmd.append("--windowed")
    cmd.append("--disable-windowed-traceback")

    # 添加图标（如果存在）
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])

    # 添加数据目录和文件
    for src, dst in DATA_DIRS:
        if os.path.exists(src):
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    for src, dst in DATA_FILES:
        if os.path.exists(src):
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    # 添加隐式导入
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    # 排除不需要的模块
    for exc in EXCLUDES:
        cmd.extend(["--exclude-module", exc])

    # 平台特定配置
    target_suffix = ""

    if system == "windows":
        target_suffix = "windows"
        # Windows 下设置通用名称
        print("[Platform] Windows — 启用 Windows 特定配置")

    elif system == "darwin":
        target_suffix = "macos"
        # macOS 上尝试使用 .icns 图标（回退 .ico）
        icns_path = "src/icon/icon.icns"
        if os.path.exists(icns_path):
            # 替换为 .icns
            icon_idx = cmd.index("--icon")
            cmd[icon_idx + 1] = icns_path
            print("[Platform] macOS — 使用 .icns 图标")
        else:
            print("[Platform] macOS — 未找到 .icns，使用 .ico（建议 macOS 使用 .icns）")

        # macOS Bundle Identifier
        cmd.extend([
            "--osx-bundle-identifier",
            "com.modeldownloader.app",
        ])

        print("[Platform] macOS — 启用 macOS 特定配置")

    elif system == "linux":
        target_suffix = "linux"
        print("[Platform] Linux — 启用 Linux 特定配置")

    else:
        print(f"[Warning] 未知平台: {system}，使用默认配置")

    # 添加主脚本
    cmd.append(MAIN_SCRIPT)

    # 显示命令
    print(f"\n[Build] 打包命令:")
    print(f"  {' '.join(cmd)}\n")

    # 执行打包
    subprocess.run(cmd, check=True)

    # ========== 验证打包结果 ==========
    output_path = os.path.join(OUTPUT_DIR, APP_NAME)
    if onefile:
        if system == "windows":
            exe_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}.exe")
            success = os.path.exists(exe_path)
            if success:
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"\n[✓] 打包成功！单文件: {exe_path} ({size_mb:.2f} MB)")
        elif system == "darwin":
            # --onefile on macOS produces a .app
            app_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}.app")
            success = os.path.exists(app_path)
            if success:
                print(f"\n[✓] 打包成功！输出: {app_path}")
        else:
            binary = os.path.join(OUTPUT_DIR, APP_NAME)
            success = os.path.exists(binary)
            if success:
                size_mb = os.path.getsize(binary) / (1024 * 1024)
                print(f"\n[✓] 打包成功！输出: {binary} ({size_mb:.2f} MB)")
    else:
        success = os.path.isdir(output_path)
        if success:
            total_size = 0
            for dirpath, _, filenames in os.walk(output_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            size_mb = total_size / (1024 * 1024)
            print(f"\n[✓] 打包成功！目录: {output_path}/ ({size_mb:.2f} MB)")

    return success


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="一键打包脚本 — 自动检测系统平台并打包对应 APP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build.py                    # 自动检测当前平台并打包
  python build.py --platform windows # 强制打包 Windows 版本
  python build.py --no-clean         # 跳过清理旧构建
  python build.py --onefile          # 打包为单个文件（默认是目录模式）
        """,
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "auto"],
        default="auto",
        help="目标平台（默认: auto，自动检测当前平台）",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="打包前清理旧构建产物（默认开启）",
    )
    parser.add_argument(
        "--no-clean",
        action="store_false",
        dest="clean",
        help="跳过清理步骤",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        default=False,
        help="打包为单个可执行文件（默认打包为目录模式）",
    )

    args = parser.parse_args()

    # 显示横幅
    print("=" * 55)
    print(f"   {APP_NAME} — 一键打包脚本")
    print("=" * 55)

    # 获取系统信息
    system, arch = get_os_info()
    print(f"\n[System]  操作系统: {system}")
    print(f"[System]  架构:     {arch}")
    print(f"[System]  Python:   {platform.python_version()}")

    # 确定目标平台
    target = args.platform
    if target == "auto":
        target = system
        if target == "darwin":
            target = "macos"

    print(f"[Target]  目标平台: {target}")
    print(f"[Target]  打包模式: {'单文件' if args.onefile else '目录模式'}")

    # 检查工作目录
    if not os.path.exists(MAIN_SCRIPT):
        print(f"\n[Error] 找不到主脚本 '{MAIN_SCRIPT}'！")
        print("  请确保在项目根目录下运行此脚本。")
        sys.exit(1)

    # Step 1: 清理
    if args.clean:
        print(f"\n{'=' * 55}")
        print("  Step 1/3: 清理构建产物")
        print(f"{'=' * 55}")
        clean_build()
    else:
        print(f"\n[Skip] 跳过清理步骤")

    # Step 2: 检查依赖
    print(f"\n{'=' * 55}")
    print("  Step 2/3: 检查依赖")
    print(f"{'=' * 55}")
    check_pyinstaller()

    # Step 3: 打包
    print(f"\n{'=' * 55}")
    print("  Step 3/3: 开始打包")
    print(f"{'=' * 55}")

    try:
        success = build_app(target, arch, args.onefile)
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] 打包失败！错误码: {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Error] 打包异常: {e}")
        sys.exit(1)

    if success:
        print(f"\n{'=' * 55}")
        print(f"  ✓✓✓  打包完成！  ✓✓✓")
        if args.onefile:
            if target == "windows":
                print(f"  输出: {os.path.join(OUTPUT_DIR, APP_NAME)}.exe")
            elif target == "macos":
                print(f"  输出: {os.path.join(OUTPUT_DIR, APP_NAME)}.app")
            else:
                print(f"  输出: {os.path.join(OUTPUT_DIR, APP_NAME)}")
        else:
            print(f"  输出: {os.path.join(OUTPUT_DIR, APP_NAME)}/")
        print(f"{'=' * 55}")
    else:
        print(f"\n[Error] 打包失败，输出未生成！")
        sys.exit(1)


if __name__ == "__main__":
    main()
