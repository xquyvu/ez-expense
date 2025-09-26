# GitHub Actions Build & Code Signing Setup

This guide explains how to set up automated macOS app building, code signing, and distribution using GitHub Actions.

## Overview

The GitHub Actions workflow will:

1. **Build** your app on macOS, Linux, and Windows
2. **Code sign** and **notarize** the macOS version (prevents Gatekeeper blocking)
3. **Create DMG installer** for easy distribution
4. **Generate Homebrew cask** for package manager installation
5. **Create GitHub releases** with all artifacts

## Required GitHub Secrets

To enable code signing and notarization, add these secrets to your GitHub repository:

### 1. Apple Developer Account Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret:

| Secret Name                      | Description                                    | How to Get                                                                |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------- |
| `APPLE_DEVELOPER_ID_APPLICATION` | Your Developer ID Application certificate name | Found in Keychain Access: "Developer ID Application: Your Name (TEAM_ID)" |
| `APPLE_TEAM_ID`                  | Your Apple Developer Team ID                   | Apple Developer Account → Membership → Team ID                            |
| `APPLE_ID`                       | Your Apple ID email                            | The email you use for Apple Developer                                     |
| `APPLE_PASSWORD`                 | App-specific password                          | [Create here](https://support.apple.com/en-us/102654)                     |

### 2. Certificate Secrets

| Secret Name                    | Description                       | How to Get                                   |
| ------------------------------ | --------------------------------- | -------------------------------------------- |
| `SIGNING_CERTIFICATE_P12_DATA` | Base64 encoded .p12 certificate   | Export from Keychain Access (see below)      |
| `SIGNING_CERTIFICATE_PASSWORD` | Password for the .p12 certificate | The password you set when exporting          |
| `KEYCHAIN_PASSWORD`            | Temporary keychain password       | Any secure password (used only during build) |

## Setting Up Code Signing Certificate

### Step 1: Get a Developer ID Certificate

1. Go to [Apple Developer Portal](https://developer.apple.com/account/resources/certificates/list)
2. Click "+" to create a new certificate
3. Select "Developer ID Application"
4. Follow the instructions to create and download the certificate
5. Double-click to install it in your Keychain

### Step 2: Export Certificate as P12

1. Open **Keychain Access**
2. Find your "Developer ID Application" certificate
3. Right-click → Export
4. Choose format: **Personal Information Exchange (.p12)**
5. Set a secure password
6. Save the file

### Step 3: Convert P12 to Base64

```bash
# Convert your certificate to base64
base64 -i /path/to/your/certificate.p12 | pbcopy
```

Paste this base64 string as the `SIGNING_CERTIFICATE_P12_DATA` secret.

## Workflow Triggers

### Automatic Triggers

- **Tag push**: `git tag v1.0.0 && git push --tags`
- **Pull Request**: For testing builds (unsigned)

### Manual Trigger

- Go to Actions → Build and Release → Run workflow
- Choose release type: draft, prerelease, or release

## Usage Examples

### Create a Release

```bash
# Tag and push to trigger a release build
git tag v1.0.0
git push --tags
```

### Test Build (No Signing)

```bash
# Create PR to test builds without signing
git checkout -b test-build
git push origin test-build
# Create PR from GitHub UI
```

## Distribution Options

Once built, your app can be distributed via:

### 1. Direct Download (Automatic)

- Users download the DMG from GitHub Releases
- Drag app to Applications folder
- **No security warnings** (if properly signed/notarized)

### 2. Homebrew Cask (Semi-Automatic)

```bash
# The workflow generates a cask file
# You'll need to submit it to homebrew-cask or create your own tap

# Users can then install via:
brew install --cask your-org/your-tap/ez-expense
```

### 3. Manual Installation Fallback

If unsigned, users can bypass warnings:

```bash
# Right-click app → Open, or:
xattr -cr /Applications/EZ-Expense.app
```

## Troubleshooting

### Certificate Issues

- Verify certificate is valid: `security find-identity -v`
- Check certificate name matches secret exactly
- Ensure Team ID is correct

### Notarization Issues

- App-specific password must be generated from Apple ID account
- Team ID must match your developer account
- App must be properly signed before notarization

### Build Issues

- Check workflow logs in GitHub Actions tab
- Verify all secrets are set correctly
- Ensure PyInstaller spec file is compatible

## Security Notes

- **Never commit certificates or passwords**
- Use app-specific passwords, not your main Apple ID password
- Rotate secrets periodically
- Consider using separate Apple ID for CI/CD

## Cost Considerations

- **Apple Developer Account**: $99/year (required for code signing)
- **GitHub Actions**: Free for public repos, paid for private repos
- **Notarization**: Free (included with Developer Account)

## Alternative: Unsigned Distribution

If you don't want to pay for Apple Developer Account:

1. Comment out signing steps in the workflow
2. Users will see security warnings
3. Provide clear instructions for bypassing warnings
4. Consider distributing via trusted package managers

## Next Steps

1. Set up the required secrets in your GitHub repository
2. Create a test tag to trigger the workflow
3. Verify the build completes successfully
4. Test the signed app on a clean macOS system
5. Set up your distribution method (direct download, Homebrew, etc.)
