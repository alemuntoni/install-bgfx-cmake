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
      bgfx-version: 'v1.157.9470-570'
      
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
| `bgfx-version` | The tag or branch of `bgfx.cmake` to clone. | `v1.157.9470-570` |
| `cache` | Whether to cache the installation (`'true'` or `'false'`). | `'true'` |
| `cache-key-prefix` | Prefix string for the GitHub cache key. | `bgfx-install` |

## Environment Variables

This action automatically exports `CMAKE_PREFIX_PATH` pointing to the cached `bgfx` installation directory.