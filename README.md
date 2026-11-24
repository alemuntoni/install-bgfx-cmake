# Install bgfx (CMake)

A GitHub Composite Action to set up and install [bgfx](https://github.com/bkaradzic/bgfx) (via [bgfx.cmake](https://github.com/bkaradzic/bgfx.cmake)) across multiple platforms (Linux, macOS, Windows). 

This action automatically handles:
- Checking and downloading precompiled releases built specifically by this action (supporting Linux x64 with broad glibc 2.35+ compatibility, Linux ARM64, macOS Universal binaries for Intel and Apple Silicon, and Windows x64 with MSVC) to skip compilation entirely.
- Falling back to upstream official `bgfx.cmake` releases if custom precompiled packages are not found for a requested version.
- Performing sanity verification (GLIBC compatibility check on Linux, MSVC compiler detection on Windows) on downloaded binaries with automatic fallback to source compilation if incompatible.
- Installing required system dependencies (e.g., `ninja`, and X11/Wayland development libraries on Linux) when compiling from source.
- Building the library statically and installing it in a local directory.
- Caching the build/download artifacts to speed up subsequent workflow runs.
- Setting the `CMAKE_PREFIX_PATH` environment variable so that subsequent CMake configuration steps in your workflow can seamlessly find the `bgfx` installation.

## Usage

```yaml
steps:
  - name: Checkout repository
    uses: actions/checkout@v7

  - name: Install bgfx
    uses: alemuntoni/install-bgfx-cmake@v1
    with:
      # Optional: specify the tag or branch of bgfx.cmake to clone
      bgfx-version: 'v1.172.9657-621'
      
      # Optional: enable or disable caching
      cache: 'true'
      
      # Optional: set a custom prefix for the cache key
      cache-key-prefix: 'bgfx-install'
      
      # Optional: set the CMAKE_BUILD_TYPE
      build-type: 'Release'
      
      # Optional: force compiling from source instead of downloading prebuilt release
      force-build: 'false'

      # Optional: extra arguments to pass to CMake during configuration
      cmake-args: ''

  - name: Configure Your Project
    run: cmake -S . -B build
    # CMAKE_PREFIX_PATH is automatically set by the action!
```

## Inputs

| Name | Description | Default |
| --- | --- | --- |
| `bgfx-version` | The tag or branch of `bgfx.cmake` to clone or download. | `v1.172.9657-621` |
| `cache` | Whether to cache the installation (`'true'` or `'false'`). | `'true'` |
| `cache-key-prefix` | Prefix string for the GitHub cache key. | `bgfx-install` |
| `build-type` | The CMAKE_BUILD_TYPE (e.g. `Release`, `Debug`). | `Release` |
| `force-build` | Force building from source instead of downloading prebuilt release (`'true'` or `'false'`). | `'false'` |
| `cmake-args` | Extra arguments to pass to CMake during configuration. | `''` |

## Using bgfx in CMake

Once installed by this action, `CMAKE_PREFIX_PATH` is automatically set in the workflow environment, allowing CMake to locate `bgfx` using `find_package`:

```cmake
find_package(bgfx CONFIG REQUIRED)

target_link_libraries(your_target PRIVATE bgfx::bgfx)
```

### Full Feature Support (Shader & Asset Compilation Tools)

When using `bgfx.cmake` via `find_package`, there is a known issue where CMake helper functions (such as shader compilation utilities) may fail because the underlying tool targets are not imported globally (see [issue #251](https://github.com/bkaradzic/bgfx.cmake-archived/issues/251)).

To ensure full usage across your entire CMake project, it is recommended to promote these targets to `GLOBAL` immediately after calling `find_package`:

```cmake
find_package(bgfx CONFIG REQUIRED)

# Workaround for https://github.com/bkaradzic/bgfx.cmake-archived/issues/251
set_target_properties(bgfx::bin2c PROPERTIES IMPORTED_GLOBAL TRUE)
set_target_properties(bgfx::texturec PROPERTIES IMPORTED_GLOBAL TRUE)
set_target_properties(bgfx::texturev PROPERTIES IMPORTED_GLOBAL TRUE)
set_target_properties(bgfx::geometryc PROPERTIES IMPORTED_GLOBAL TRUE)
set_target_properties(bgfx::geometryv PROPERTIES IMPORTED_GLOBAL TRUE)
set_target_properties(bgfx::shaderc PROPERTIES IMPORTED_GLOBAL TRUE)
```

## Environment Variables

This action automatically exports `CMAKE_PREFIX_PATH` pointing to the cached `bgfx` installation directory.
