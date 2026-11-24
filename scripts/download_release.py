#!/usr/bin/env python3
"""
Helper script for install-bgfx-cmake GitHub Action.
Downloads and verifies precompiled bgfx.cmake release binaries when eligible.
Falls back to building from source if ineligible, unavailable, or incompatible.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def set_output(key: str, value: str) -> None:
    """Set output parameter for GitHub Actions."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"[output] {key}={value}")


def get_release_platform(runner_os: str, runner_arch: str) -> Optional[str]:
    """
    Determine if precompiled binaries exist for this OS & architecture.
    bgfx.cmake official releases currently only provide:
      - Linux: x86_64
      - macOS: arm64 (Apple Silicon)
      - Windows: x86_64
    """
    os_name = runner_os.strip().lower()
    arch_name = runner_arch.strip().lower()

    if os_name == "linux":
        if arch_name in ("x64", "x86_64", "amd64"):
            return "linux"
        print(f"Precompiled releases are only available for Linux x86_64 (runner arch: {runner_arch}).")
        return None

    if os_name == "macos":
        if arch_name in ("arm64", "aarch64"):
            return "macos"
        print(f"Precompiled releases are only available for macOS ARM64 (runner arch: {runner_arch}).")
        return None

    if os_name == "windows":
        if arch_name in ("x64", "x86_64", "amd64"):
            return "windows"
        print(f"Precompiled releases are only available for Windows x86_64 (runner arch: {runner_arch}).")
        return None

    print(f"Unsupported OS: {runner_os}")
    return None


def download_release(version: str, platform: str, dest_archive: Path) -> bool:
    """Download the precompiled tarball from GitHub Releases."""
    url = (
        f"https://github.com/bkaradzic/bgfx.cmake/releases/download/"
        f"{version}/bgfx.cmake.binary.{platform}.{version}.tar.gz"
    )
    print(f"Checking and downloading precompiled release from: {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "install-bgfx-cmake-action"}
    )
    try:
        with urllib.request.urlopen(req) as resp, open(dest_archive, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        return True
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} while downloading {url}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"Network error while downloading {url}: {e.reason}")
        return False
    except Exception as e:
        print(f"Unexpected error while downloading {url}: {e}")
        return False


def extract_tar_strip_root(tar_path: Path, dest_dir: Path) -> None:
    """Extract tar.gz into dest_dir stripping the leading 'bgfx.cmake/' directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = []
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if len(parts) <= 1:
                # Top-level directory itself, skip
                continue
            # Strip the leading component
            member.name = str(Path(*parts[1:]))
            members.append(member)

        # Support filter='data' on Python 3.12+ for secure extraction
        kwargs = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        tar.extractall(path=dest_dir, members=members, **kwargs)


def verify_binary(install_dir: Path, runner_os: str) -> bool:
    """
    Sanity check: verify that shaderc can execute on the runner.
    Catches dynamic linking issues such as GLIBC or runtime incompatibilities on Linux.
    """
    bin_name = "shaderc.exe" if runner_os == "Windows" else "shaderc"
    shaderc_path = install_dir / "bin" / bin_name

    if not shaderc_path.is_file():
        # If there is no shaderc executable, nothing to verify
        return True

    # Ensure executable permissions on POSIX
    if runner_os != "Windows":
        try:
            mode = shaderc_path.stat().st_mode
            shaderc_path.chmod(mode | 0o755)
        except OSError as e:
            print(f"Warning: failed to chmod {shaderc_path}: {e}")

    try:
        res = subprocess.run(
            [str(shaderc_path), "-v"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            print(f"Sanity check failed for {shaderc_path}: process returned {res.returncode}")
            if res.stderr:
                print(f"stderr: {res.stderr.strip()}")
            return False
        print(f"Sanity check succeeded: {res.stdout.strip()}")
        return True
    except (subprocess.SubprocessError, OSError) as e:
        print(f"Sanity check failed for {shaderc_path}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify precompiled bgfx.cmake release")
    parser.add_argument("--version", required=True, help="bgfx.cmake version/tag")
    parser.add_argument("--install-dir", required=True, help="Installation directory path")
    parser.add_argument("--runner-os", required=True, help="RUNNER_OS (Linux, macOS, Windows)")
    parser.add_argument("--runner-arch", required=True, help="RUNNER_ARCH (X64, ARM64, etc.)")
    args = parser.parse_args()

    install_dir = Path(args.install_dir).resolve()
    platform = get_release_platform(args.runner_os, args.runner_arch)
    if not platform:
        print("Platform not eligible for precompiled download. Falling back to build from source.")
        set_output("installed", "false")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "bgfx-release.tar.gz"
        if not download_release(args.version, platform, archive_path):
            print("Precompiled release not found or failed to download. Falling back to build from source.")
            set_output("installed", "false")
            return

        print(f"Extracting release archive to {install_dir}...")
        try:
            extract_tar_strip_root(archive_path, install_dir)
        except Exception as e:
            print(f"Failed to extract release archive: {e}")
            if install_dir.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
            set_output("installed", "false")
            return

    # Ensure executable permissions on all files in bin/ on Unix
    if args.runner_os != "Windows":
        bin_dir = install_dir / "bin"
        if bin_dir.is_dir():
            for f in bin_dir.iterdir():
                if f.is_file():
                    try:
                        f.chmod(f.stat().st_mode | 0o755)
                    except OSError:
                        pass

    # Sanity check: test if shaderc executes (GLIBC / ABI verification)
    if not verify_binary(install_dir, args.runner_os):
        print("Sanity verification failed (e.g. GLIBC or runtime incompatibility). Falling back to build from source.")
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)
        set_output("installed", "false")
        return

    print("Precompiled bgfx release successfully downloaded, extracted, and verified.")
    set_output("installed", "true")


if __name__ == "__main__":
    main()
