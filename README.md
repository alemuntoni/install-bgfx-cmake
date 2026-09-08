# Install bgfx (CMake)

A GitHub Composite Action to build and install [bgfx](https://github.com/bkaradzic/bgfx) (via [bgfx.cmake](https://github.com/bkaradzic/bgfx.cmake)) across multiple platforms (Linux, macOS, Windows). 

This action automatically handles:
- Installing required system dependencies (e.g., `ninja`, and X11/Wayland development libraries on Linux).
- Cloning the `bgfx.cmake` repository at the specified version.
- Building the library statically and installing it in a local directory.
- Caching the build artifacts to speed up subsequent workflow runs.
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
      bgfx-version: 'v1.159.9479-572'
      
      # Optional: enable or disable caching
      cache: 'true'
      
      # Optional: set a custom prefix for the cache key
      cache-key-prefix: 'bgfx-install'

  - name: Configure Your Project
    run: cmake -S . -B build
    # CMAKE_PREFIX_PATH is automatically set by the action!
```

## Inputs

| Name | Description | Default |
| --- | --- | --- |
| `bgfx-version` | The tag or branch of `bgfx.cmake` to clone. | `v1.159.9479-572` |
| `cache` | Whether to cache the installation (`'true'` or `'false'`). | `'true'` |
| `cache-key-prefix` | Prefix string for the GitHub cache key. | `bgfx-install` |

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