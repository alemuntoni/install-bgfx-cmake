#!/usr/bin/env python3
"""
Helper script for install-bgfx-cmake GitHub Action.
Downloads and verifies precompiled bgfx.cmake release binaries using a multi-tiered approach:
  1. Priority 1: Search releases of alemuntoni/install-bgfx-cmake via GitHub API
     to locate matching precompiled assets across all action releases (e.g. v1.0.13).
  2. Priority 2: Fallback to upstream bkaradzic/bgfx.cmake official releases.
  3. Priority 3: Fallback cleanly to building from source if unavailable or incompatible.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

CUSTOM_REPO = "alemuntoni/install-bgfx-cmake"
UPSTREAM_REPO = "bkaradzic/bgfx.cmake"


def set_output(key: str, value: str) -> None:
    """Set output parameter for GitHub Actions."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"[output] {key}={value}")


def get_target_custom_asset_names(version: str, runner_os: str, runner_arch: str, build_type: str = "Release") -> List[str]:
    """
    Generate candidate asset filenames for alemuntoni/install-bgfx-cmake releases.
    """
    os_name = runner_os.strip().lower()
    arch_name = runner_arch.strip().lower()
    norm_arch = "arm64" if arch_name in ("arm64", "aarch64") else ("x64" if arch_name in ("x64", "x86_64", "amd64") else arch_name)
    is_debug = build_type.strip().lower() == "debug"

    names: List[str] = []
    if os_name == "linux":
        if norm_arch in ("x64", "arm64"):
            names.append(f"bgfx-install-linux-{norm_arch}-{version}.tar.gz")
    elif os_name == "macos":
        # Check universal first (covers both Intel and Apple Silicon)
        names.append(f"bgfx-install-macos-universal-{version}.tar.gz")
        if norm_arch in ("arm64", "x64"):
            names.append(f"bgfx-install-macos-{norm_arch}-{version}.tar.gz")
    elif os_name == "windows":
        if norm_arch == "x64":
            if is_debug:
                names.append(f"bgfx-install-windows-x64-Debug-{version}.tar.gz")
            else:
                names.append(f"bgfx-install-windows-x64-{version}.tar.gz")

    return names


def find_asset_in_custom_repo(repo: str, target_names: List[str], token: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Query GitHub API to search for target assets across the releases of the repository.
    Returns (asset_name, browser_download_url) or None if not found.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page=50"
    headers = {"User-Agent": "install-bgfx-cmake-action"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"Searching for precompiled asset {target_names} in {repo} releases...")
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read().decode("utf-8"))
            for release in releases:
                tag = release.get("tag_name", "unknown")
                for asset in release.get("assets", []):
                    asset_name = asset.get("name")
                    if asset_name in target_names:
                        download_url = asset.get("browser_download_url")
                        if download_url:
                            print(f"Found matching precompiled asset '{asset_name}' in release {tag}: {download_url}")
                            return asset_name, download_url
    except urllib.error.HTTPError as e:
        print(f"GitHub API query error ({e.code} {e.reason}) while searching {repo} releases.")
    except Exception as e:
        print(f"Warning: could not query GitHub API for {repo}: {e}")

    return None


def get_upstream_download_url(version: str, runner_os: str, runner_arch: str, build_type: str = "Release") -> Optional[str]:
    """
    Generate download URL for official upstream bkaradzic/bgfx.cmake releases.
    Upstream officially only publishes Linux x86_64, macOS arm64, Windows x86_64 in Release mode.
    """
    if build_type.strip().lower() != "release":
        return None

    os_name = runner_os.strip().lower()
    arch_name = runner_arch.strip().lower()
    norm_arch = "arm64" if arch_name in ("arm64", "aarch64") else ("x64" if arch_name in ("x64", "x86_64", "amd64") else arch_name)

    base = f"https://github.com/{UPSTREAM_REPO}/releases/download/{version}"
    if os_name == "linux" and norm_arch == "x64":
        return f"{base}/bgfx.cmake.binary.linux.{version}.tar.gz"
    elif os_name == "macos" and norm_arch == "arm64":
        return f"{base}/bgfx.cmake.binary.macos.{version}.tar.gz"
    elif os_name == "windows" and norm_arch == "x64":
        return f"{base}/bgfx.cmake.binary.windows.{version}.tar.gz"

    return None


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file via HTTP/HTTPS, following redirects."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "install-bgfx-cmake-action"}
    )
    try:
        with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        return True
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} ({e.reason}) for {url}")
        return False
    except urllib.error.URLError as e:
        print(f"Network error ({e.reason}) for {url}")
        return False
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False


def extract_tar_archive(tar_path: Path, dest_dir: Path) -> None:
    """
    Extract tar.gz into dest_dir.
    Intelligently detects if there is an outer container directory (e.g. 'bgfx.cmake/')
    and strips it, or extracts root-level files/directories (bin/, include/, lib/) directly.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        if not members:
            return

        # Check if archive has an outer wrapper directory (e.g. bgfx.cmake/bin vs ./bin or bin/)
        first_components = set()
        for m in members:
            parts = Path(m.name).parts
            if parts:
                first_components.add(parts[0])

        known_roots = {"bin", "include", "lib", "share", "."}
        strip_outer = (len(first_components) == 1) and not (first_components.issubset(known_roots))

        filtered_members = []
        for member in members:
            parts = Path(member.name).parts
            if not parts:
                continue
            if strip_outer:
                if len(parts) <= 1:
                    continue
                member.name = str(Path(*parts[1:]))
            elif parts[0] == ".":
                if len(parts) <= 1:
                    continue
                member.name = str(Path(*parts[1:]))
            filtered_members.append(member)

        kwargs = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        tar.extractall(path=dest_dir, members=filtered_members, **kwargs)


def verify_binary(install_dir: Path, runner_os: str) -> bool:
    """
    Sanity check: verify that shaderc can execute on the runner.
    Detects dynamic library mismatches (e.g. GLIBC version on Linux).
    """
    bin_name = "shaderc.exe" if runner_os == "Windows" else "shaderc"
    shaderc_path = install_dir / "bin" / bin_name

    if not shaderc_path.is_file():
        # If no shaderc executable in bin/, nothing to verify
        return True

    # Ensure executable permissions on POSIX
    if runner_os != "Windows":
        try:
            mode = shaderc_path.stat().st_mode
            shaderc_path.chmod(mode | 0o755)
        except OSError:
            pass

    try:
        res = subprocess.run(
            [str(shaderc_path), "-v"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            print(f"Sanity check failed for {shaderc_path}: process exited with code {res.returncode}")
            if res.stderr:
                print(f"stderr: {res.stderr.strip()}")
            return False
        print(f"Sanity check succeeded: {res.stdout.strip()}")
        return True
    except (subprocess.SubprocessError, OSError) as e:
        print(f"Sanity check failed for {shaderc_path}: {e}")
        return False


def is_msvc_compiler() -> bool:
    """
    Check if CMake's default C++ compiler on Windows is MSVC.
    Runs a lightweight CMake configuration probe.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cmakelists = Path(tmpdir) / "CMakeLists.txt"
        cmakelists.write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(compiler_probe LANGUAGES CXX)\n"
            "file(WRITE \"${CMAKE_BINARY_DIR}/compiler_id.txt\" \"${CMAKE_CXX_COMPILER_ID}\")\n"
        )
        build_dir = Path(tmpdir) / "build"
        try:
            cmd = ["cmake", "-S", str(tmpdir), "-B", str(build_dir)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            compiler_id_file = build_dir / "compiler_id.txt"
            if compiler_id_file.is_file():
                compiler_id = compiler_id_file.read_text().strip()
                print(f"Detected default CMake CXX compiler on Windows: {compiler_id}")
                return compiler_id == "MSVC"

            if "The CXX compiler identification is MSVC" in res.stdout:
                print("Detected MSVC from CMake output.")
                return True
            if "The CXX compiler identification is" in res.stdout:
                for line in res.stdout.splitlines():
                    if "The CXX compiler identification is" in line:
                        print(f"Detected non-MSVC compiler: {line.strip()}")
                return False
        except Exception as e:
            print(f"Warning: CMake compiler probe failed ({e}). Checking environment...")

        # Fallback check if cl.exe is in PATH or Visual Studio environment is active
        if shutil.which("cl") is not None:
            print("Found cl.exe in PATH, assuming MSVC.")
            return True
        if "VCINSTALLDIR" in os.environ or "VSINSTALLDIR" in os.environ:
            print("Visual Studio environment variables detected, assuming MSVC.")
            return True

        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify precompiled bgfx.cmake release")
    parser.add_argument("--version", required=True, help="bgfx.cmake version/tag")
    parser.add_argument("--build-type", default="Release", help="CMAKE_BUILD_TYPE (Release, Debug)")
    parser.add_argument("--install-dir", required=True, help="Installation directory path")
    parser.add_argument("--runner-os", required=True, help="RUNNER_OS (Linux, macOS, Windows)")
    parser.add_argument("--runner-arch", required=True, help="RUNNER_ARCH (X64, ARM64, etc.)")
    args = parser.parse_args()

    install_dir = Path(args.install_dir).resolve()
    token = os.environ.get("GITHUB_TOKEN") or None

    # On Windows, precompiled binaries are compiled with MSVC.
    # Check if the host CMake compiler is MSVC; if not (e.g. MinGW/Clang), skip download and build from source.
    if args.runner_os.strip().lower() == "windows":
        if not is_msvc_compiler():
            print("Default CMake compiler on Windows is not MSVC. Skipping precompiled download to build from source.")
            set_output("installed", "false")
            return

    download_succeeded = False
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "bgfx-release.tar.gz"

        # Tier 1: Search in custom repo (alemuntoni/install-bgfx-cmake) across all releases
        custom_target_names = get_target_custom_asset_names(
            args.version, args.runner_os, args.runner_arch, build_type=args.build_type
        )
        if custom_target_names:
            asset_info = find_asset_in_custom_repo(CUSTOM_REPO, custom_target_names, token=token)
            if asset_info:
                asset_name, download_url = asset_info
                print(f"Attempting download of custom precompiled asset: {download_url}")
                if download_file(download_url, archive_path):
                    print(f"Successfully downloaded {asset_name} from {CUSTOM_REPO}.")
                    try:
                        extract_tar_archive(archive_path, install_dir)
                        download_succeeded = True
                    except Exception as e:
                        print(f"Failed to extract archive: {e}")
                        if install_dir.exists():
                            shutil.rmtree(install_dir, ignore_errors=True)
                        archive_path.unlink(missing_ok=True)

        # Tier 2: Fallback to upstream bkaradzic/bgfx.cmake
        if not download_succeeded:
            upstream_url = get_upstream_download_url(
                args.version, args.runner_os, args.runner_arch, build_type=args.build_type
            )
            if upstream_url:
                print(f"Checking precompiled release from upstream {UPSTREAM_REPO}: {upstream_url}")
                if download_file(upstream_url, archive_path):
                    print(f"Successfully downloaded archive from upstream {UPSTREAM_REPO}.")
                    try:
                        extract_tar_archive(archive_path, install_dir)
                        download_succeeded = True
                    except Exception as e:
                        print(f"Failed to extract upstream archive: {e}")
                        if install_dir.exists():
                            shutil.rmtree(install_dir, ignore_errors=True)

        # Tier 3: If neither succeeded, fallback to build
        if not download_succeeded:
            print("No matching precompiled release found or downloaded.")
            print("Falling back to building bgfx from source.")
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

    # Sanity check: test if shaderc executes (GLIBC / ABI check)
    if not verify_binary(install_dir, args.runner_os):
        print("Sanity verification failed (e.g. GLIBC or runtime incompatibility).")
        print("Falling back to building bgfx from source.")
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)
        set_output("installed", "false")
        return

    print("Precompiled bgfx release successfully installed and verified.")
    set_output("installed", "true")


if __name__ == "__main__":
    main()
