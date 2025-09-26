# macOS Distribution Options Summary

You have multiple ways to distribute your macOS app to avoid Gatekeeper blocking:

## 🚀 Quick Start (Recommended for Testing)

Use the **simple build workflow** that requires no setup:

1. The app will be unsigned (users see warnings but can bypass them)
2. No Apple Developer Account needed ($0 cost)
3. Works immediately with your existing setup

**Trigger a build:**

```bash
git tag v1.0.0
git push --tags
```

## 🔐 Professional Distribution (Recommended for Production)

Use the **full build workflow** with code signing:

1. **Pros:** No user warnings, professional appearance, trusted by macOS
2. **Cons:** Requires Apple Developer Account ($99/year) and setup
3. **Best for:** Apps you plan to distribute widely

**Setup required:** Follow `GITHUB_ACTIONS_SETUP.md`

## 📦 Distribution Methods Comparison

| Method                        | User Experience | Setup Complexity | Cost     | Security Warnings    |
| ----------------------------- | --------------- | ---------------- | -------- | -------------------- |
| **GitHub Actions (Signed)**   | ⭐⭐⭐⭐⭐ Perfect   | 🔧🔧🔧 Complex      | $99/year | ❌ None               |
| **GitHub Actions (Unsigned)** | ⭐⭐⭐ Good        | 🔧 Simple         | Free     | ⚠️ Bypassable         |
| **Homebrew Cask**             | ⭐⭐⭐⭐⭐ Perfect   | 🔧🔧 Medium        | Free*    | ❌ None (if signed)   |
| **Direct Download**           | ⭐⭐⭐ Good        | 🔧 Simple         | Free     | ⚠️ Depends on signing |

*Homebrew cask submission is free, but signing requires Developer Account

## 🏆 Recommendation Based on YTMD Success

Looking at the YouTube Music Desktop app (YTMD) that you mentioned works without blocking:

1. **They use Homebrew distribution**: `brew install th-ch/youtube-music/youtube-music`
2. **They provide signed releases**: No security warnings for users
3. **They use GitHub Actions**: Automated builds with proper code signing
4. **Multiple platforms**: macOS, Linux, Windows support

**For your app, I recommend:**

### Phase 1: Quick Launch (Now)

- Use `simple-build.yml` workflow
- Users can bypass warnings with right-click → Open
- Get user feedback and validate your app

### Phase 2: Professional Release (Later)

- Get Apple Developer Account
- Set up `build-and-release.yml` workflow
- Create Homebrew tap for easy installation
- No more user warnings

## 🚦 Getting Started

1. **Commit the workflows:**

```bash
git add .github/workflows/
git commit -m "Add GitHub Actions workflows for automated builds"
git push
```

2. **Create your first release:**

```bash
git tag v1.0.0
git push --tags
```

3. **Monitor the build:**

- Go to your GitHub repository
- Click "Actions" tab
- Watch the build progress

4. **Download and test:**

- Once complete, go to "Releases"
- Download the ZIP file
- Test the installation process

## 🔧 Files Added

- `.github/workflows/build-and-release.yml` - Full workflow with code signing
- `.github/workflows/simple-build.yml` - Simple workflow without signing
- `deployment/GITHUB_ACTIONS_SETUP.md` - Detailed setup guide
- `deployment/build-macos-signed.sh` - Local build script with signing

## 📞 Support

If you encounter issues:

1. **Check GitHub Actions logs** for detailed error messages
2. **Test locally first** using the build scripts in `deployment/`
3. **Start with simple workflow** before attempting code signing
4. **Verify PyInstaller spec** works on your development machine

## 🎯 Next Steps

1. Test the simple build workflow first
2. Get user feedback on your app
3. Consider upgrading to signed builds when ready
4. Set up Homebrew tap for easier distribution

The key insight from YTMD's success is that **proper signing + convenient distribution (Homebrew) = great user experience**. But you can start simple and upgrade later!

## Previous Deployment Tools

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

### After `./deploy.sh build`

- `../dist/ez-expense` - Standalone executable
- `../dist/EZ-Expense.app` - macOS app bundle

### After `./deploy.sh releases`

- `../releases/ez-expense-macos.zip` - macOS release package
- `../releases/ez-expense-windows.zip` - Windows release package

Each package contains executable, user guide, configuration template, and platform-specific launchers.

## Requirements

- Python 3.8+ with uv package manager (recommended)
- PyInstaller
- All project dependencies installed

The build process automatically installs PyInstaller and Playwright browsers as needed.
