# EZ-Expense Deployment Tools

This folder contains all the tools and files needed to build and distribute the EZ-Expense application as standalone executables for GitHub releases.

## Quick Start

### For GitHub Releases (Primary Method)

```bash
# Build GitHub release packages (macOS + Windows)
./deploy.sh releases
```

This creates `../releases/` folder with ZIP files ready for GitHub releases.

### For Development

```bash
# Build executable only
./deploy.sh build

# Test the build
./deploy.sh test

# Run the application
./deploy.sh run
```

## Files in this folder

### Core Build Files

- `build.sh` / `build.bat` - Build executable using PyInstaller
- `ez-expense.spec` - PyInstaller configuration
- `hooks/hook-playwright.py` - Runtime configuration for Playwright

### Release & Distribution

- `build-releases.sh` - Creates GitHub release packages (macOS + Windows)
- `test-executable.sh` - Quick executable validation
- `run-ez-expense.sh` - Development launcher script

### Documentation

- `DEPLOYMENT_GUIDE.md` - Complete deployment and CI/CD guide
- `USER_GUIDE.md` - End-user documentation
- `README.md` - This file

## How it works

### Automated CI/CD (Recommended)

1. **Tag Release**: Push a version tag (`git tag v1.0.0`)
2. **GitHub Actions**: Automatically builds both platforms
3. **Release**: Creates GitHub release with professional notes
4. **Distribution**: Users download from GitHub releases

### Manual Build Process

1. **Building**: Uses PyInstaller to bundle Python application into standalone executables
2. **Packaging**: Creates platform-specific packages with user guides and templates
3. **Distribution**: Generates ZIP files ready for upload

## Output

### After `./deploy.sh build`:

- `../dist/ez-expense` - Standalone executable
- `../dist/EZ-Expense.app` - macOS app bundle

### After `./deploy.sh releases`:

- `../releases/ez-expense-macos.zip` - macOS release package
- `../releases/ez-expense-windows.zip` - Windows release package

Each package contains executable, user guide, configuration template, and platform-specific launchers.

## Requirements

- Python 3.8+ with uv package manager (recommended)
- PyInstaller
- All project dependencies installed

The build process automatically installs PyInstaller and Playwright browsers as needed.
