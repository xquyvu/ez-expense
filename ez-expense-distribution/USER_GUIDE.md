# EZ-Expense Standalone Application

## Quick Start Guide

### What is EZ-Expense?

EZ-Expense is a tool that helps you automatically match receipts to your expense reports using AI. It can extract information from receipts and match them to existing expenses in your system.

### System Requirements

- **macOS**: 10.15 (Catalina) or later
- **Windows**: Windows 10 or later
- **Linux**: Ubuntu 18.04+ or equivalent
- **RAM**: At least 4GB available
- **Disk Space**: 500MB free space (for temporary files)

### First Time Setup

#### 1. Download and Run

- Download the `ez-expense` executable (or `EZ-Expense.app` on macOS)
- On macOS: Double-click the `.app` file or run `./ez-expense` in Terminal
- On Windows: Double-click `ez-expense.exe`
- On Linux: Run `./ez-expense` in Terminal

#### 2. Initial Browser Setup

When you first run EZ-Expense:

1. The app will automatically install the required browser components (this may take 1-2 minutes)
2. A browser window will open automatically
3. A web interface will open at `http://localhost:3000`

⚠️ **Important**: Keep the terminal/command window open while using the app!

### How to Use

#### Step 1: Import Your Expenses

1. Export your existing expenses from your expense management system (like Concur, Expensify, etc.)
2. In the EZ-Expense web interface, click "Import Expenses"
3. Upload your CSV file

#### Step 2: Upload Receipts

1. Click "Upload Receipts" in the web interface
2. Drag and drop your receipt files (PDF, JPG, PNG supported)
3. The AI will automatically extract information from each receipt

#### Step 3: Match and Verify

1. The app will automatically suggest matches between receipts and expenses
2. Review each match and confirm or correct as needed
3. Export your completed expense report

### Environment Configuration

The app needs some API keys to work properly. Create a `.env` file in the same folder as the executable:

```
# Required: Azure AI Vision (for receipt text extraction)
AZURE_AI_VISION_ENDPOINT=your_endpoint_here
AZURE_AI_VISION_KEY=your_key_here

# Required: OpenAI (for intelligent matching)
OPENAI_API_KEY=your_openai_key_here

# Optional: Browser automation settings
BROWSER_PORT=9222
FRONTEND_PORT=3000
```

### Troubleshooting

#### App Won't Start

- **macOS**: If you see "App can't be opened", right-click → Open, then click "Open" in the security dialog
- **Windows**: If Windows Defender blocks it, click "More info" → "Run anyway"
- **All platforms**: Make sure you have at least 4GB of RAM available

#### Browser Issues

- If the browser doesn't open automatically, manually go to `http://localhost:3000`
- If you see connection errors, wait 30 seconds and refresh the page

#### Performance Issues

- The app uses significant memory (200-500MB) due to browser automation
- Close other applications if your computer runs slowly
- The first startup takes longer (30-60 seconds) as components initialize

#### API Errors

- Make sure your `.env` file has valid API keys
- Check your internet connection
- Verify your Azure AI Vision and OpenAI credits/quotas

### Getting Help

If you encounter issues:

1. Check the terminal/command window for error messages
2. Ensure your `.env` file is properly configured
3. Try restarting the application
4. Check that no other applications are using ports 3000 or 9222

### Updates

To update EZ-Expense:

1. Download the new version
2. Replace the old executable with the new one
3. Your data and settings will be preserved

---

**Technical Note**: This app runs a local web server and browser automation. It's completely private - no data leaves your computer except for API calls to Azure AI Vision and OpenAI for processing.
