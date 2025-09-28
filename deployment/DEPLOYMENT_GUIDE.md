# EZ-Expense Deployment Guide

## Automated GitHub Releases

- **CI/CD**: Automatic building and releasing via GitHub Actions
- **Cross-Platform**: Both macOS and Windows packages created automatically
- **Professional**: Release notes and assets generated automatically

## Release Packages

Two optimized packages for end users:

### macOS Package (`ez-expense-macos.zip`)

```text
ez-expense-macos/
├── EZ-Expense.app            # Native macOS app bundle
├── USER_GUIDE.md             # Complete user guide
├── .env.template             # Configuration template
└── README.txt                # Quick start instructions
```

### Windows Package (`ez-expense-windows.zip`)

```text
ez-expense-windows/
├── ez-expense.exe            # Windows executable
├── run-ez-expense.bat        # Simple launcher
├── USER_GUIDE.md             # Complete user guide
├── .env.template             # Configuration template
└── README.txt                # Quick start instructions
```

## 🚀 How to Release

### Automated Releases (Recommended)

1. **Create a version tag**:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **GitHub Actions automatically**:
   - Builds both macOS and Windows packages
   - Creates a GitHub release
   - Uploads release assets
   - Generates professional release notes

3. **Users download** from: `https://github.com/xquyvu/ez-expense/releases`

### Manual Local Build (For Testing)

```bash
# Build releases locally for testing
./deploy.sh releases
```

This creates `releases/` folder with ZIP files ready for manual upload.

## 🛠 Available Commands

### Streamlined Deployment Commands

```bash
# Build executable only (for development/testing)
./deploy.sh build

# Test the executable
./deploy.sh test

# Build GitHub release packages (THE MAIN COMMAND)
./deploy.sh releases

# Run the application locally
./deploy.sh run
```

### Command Details

- **`releases`**: Creates both macOS and Windows packages ready for GitHub releases
- **`build`**: Just builds the executable for local testing
- **`test`**: Validates that the executable works
- **`run`**: Runs the application in development mode

## 📤 Distribution Strategy

### 1. GitHub Releases (Primary Method)

- **Automatic**: Push tags trigger releases
- **Professional**: Auto-generated release notes
- **Secure**: GitHub hosting and download analytics
- **Versioned**: Clear version management

### 2. Manual Distribution (Backup)

If needed, you can manually build and distribute:

```bash
./deploy.sh releases
# Upload the ZIP files from releases/ folder manually
```

## 🔧 Maintenance & Updates

### To Release Updates

1. **Make changes** to your code
2. **Push tag**: `git tag v1.0.1 && git push origin v1.0.1`
3. **Automatic**: GitHub Actions builds and publishes release
4. **Notify users** of the new release

### CI/CD Pipeline

The GitHub Actions workflow automatically:

- ✅ Installs dependencies with `uv`
- ✅ Builds both macOS and Windows packages
- ✅ Creates professional release notes
- ✅ Uploads release assets
- ✅ Handles all packaging and distribution

### Version Management

```bash
# Semantic versioning examples
git tag v1.0.0    # Major release
git tag v1.0.1    # Bug fix
git tag v1.1.0    # New features
```

## ⚠️ Important Notes for Users

### Security Considerations

- **macOS**: Users may see "App can't be opened" - they need to right-click → Open
- **Windows**: May be flagged by Windows Defender - users need to allow it
- **Code Signing**: Consider code signing certificates for professional distribution

### System Requirements

- **Memory**: App uses 200-500MB RAM due to browser automation
- **Browser**: Chromium is automatically installed by Playwright
- **Ports**: Uses ports 5001 and 9222 locally
- **APIs**: Requires internet for Azure AI Vision and OpenAI

### Support Strategy

1. **User Guide**: Comprehensive guide included
2. **Troubleshooting**: Common issues documented
3. **Environment File**: Clear template with instructions
4. **Launcher Scripts**: User-friendly error messages

## 🎯 Success Metrics

- ✅ **Zero Setup**: Users don't need Python, pip, or technical knowledge
- ✅ **Cross-Platform**: Works on macOS, Windows, Linux
- ✅ **Self-Contained**: All dependencies bundled

## 🔮 Future Improvements

Consider these enhancements:

1. **Auto-updater**: Automatic update mechanism
2. **Installer**: MSI/PKG installers instead of zip files
3. **GUI Config**: Replace .env file with settings dialog
4. **Crash Reporting**: Automatic error reporting

## 📞 User Support

When users have issues:

1. Check their `.env` file configuration
2. Verify API keys are valid
3. Ensure ports 5001/9222 aren't in use
4. Check system requirements (RAM, OS version)
5. Look at terminal output for error messages
