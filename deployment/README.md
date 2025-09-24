# EZ-Expense Deployment Tools

This folder contains all the tools and files needed to build and distribute the EZ-Expense application as a standalone executable.

## Quick Start

1. **Build the executable:**

   ```bash
   cd deployment/
   ./build.sh        # macOS/Linux
   # or
   build.bat         # Windows
   ```

2. **Test the build:**

   ```bash
   ./test-executable.sh
   ```

3. **Create distribution package:**

   ```bash
   ./package.sh
   ```

4. **Run the application:**

   ```bash
   ./run-ez-expense.sh
   ```

## Files in this folder

### Build Files

- `ez-expense.spec` - PyInstaller configuration
- `build.sh` / `build.bat` - Cross-platform build scripts
- `hooks/hook-playwright.py` - Runtime configuration for Playwright

### Distribution Files

- `package.sh` - Creates user-friendly distribution package
- `run-ez-expense.sh` - User-friendly launcher script
- `test-executable.sh` - Quick executable validation

### Documentation

- `DEPLOYMENT_GUIDE.md` - Comprehensive deployment guide
- `USER_GUIDE.md` - End-user documentation

## How it works

1. **Building**: The build scripts use PyInstaller to bundle the Python application into a standalone executable
2. **Packaging**: The package script creates a distribution folder with all necessary files for end users
3. **Distribution**: Users get a simple folder with an executable and documentation

## Output

After building, you'll find:

- `../dist/ez-expense` - The standalone executable
- `../dist/EZ-Expense.app` - macOS app bundle (macOS only)

After packaging, you'll find:

- `ez-expense-distribution/` - Ready-to-distribute folder
- Contains executable, documentation, and configuration templates

## Requirements

- Python 3.8+ with uv package manager (recommended)
- PyInstaller
- All project dependencies installed

The build process automatically installs PyInstaller and Playwright browsers as needed.
