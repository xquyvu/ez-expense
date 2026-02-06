# EZ-Expense Standalone Application

EZ-Expense is a tool that helps you automatically match receipts to your expense reports using AI, then fill in the expense report in MyExpense for you.

## How to Use

### Step 0: Setup

The app needs some configuration to work properly. You'll find a `.env.template` file in the same folder as the executable.

**Setup Steps:**

1. If you don't see the file. Make sure your file explorer is set to show hidden files.
2. **Rename** `.env.template` to `.env`
3. **Edit** the file with your settings, following the instructions in the file.
   - Set your Azure OpenAI configuration (endpoint, API key, model name)
   - Configure `DATE_FORMAT` to match your region (e.g., `DD/MM/YYYY` for UK, `MM/DD/YYYY` for US)

**Additional instructions for MacOS:**

This app is not code-signed (requires $99/year Apple Developer Account). macOS will show a security warning, but you can safely bypass it by right-clicking the app and selecting "Open", or using:

```bash
# After installing the app, replace this with the path to where you extracted the zip file
/usr/bin/xattr -cr <path_to_your_extracted_package>/EZ-Expense.app
/usr/bin/xattr -cr <path_to_your_extracted_package>/ez-expense
```

### Step 1: Import Your Expenses

When you launch the app, it will open MyExpense page, and also a local web interface in your default browser.

1. Follow the instructions in the MyExpense app to navigate to your expense report in
   MyExpense
2. Import your expenses from MyExpense into the EZ-Expense app by clicking on the
   `Import from My Expense` button in the web interface. The app will automatically
   fetch your expenses by clicking through the MyExpense page.

### Step 2: Upload and match receipts

There are multiple ways to upload receipts:

#### Using the bulk upload area (recommended)

**This is the ideal workflow, which allows you to upload multiple receipts at once, and
match them to multiple expenses in one go. It can also create new expenses for receipts
that don't match any existing expenses.**

1. Drag and drop receipts into the `Bulk Receipt Upload` area, or clicking on the
"Attach Receipts" button and select the receipt files you want to process.

1. Click on "Match receipts with expenses" to start the matching process. The app will
automatically attach receipts to expenses based on the invoice amount and date

#### Uploading receipts to an existing expense

You can also upload receipts directly to an expense by clicking on the `Upload Receipt`
button next to each expense item. This is useful if you want to match a receipt to a
specific expense.

If you do it this way, no validation will be performed to check if the receipt matches
the expense. It will just attach the receipt to the expense.

### Step 3: Review and adjust if needed

After the matching process is complete, review the matched expenses and receipts. You
will also need to manually enter the missing information such as:

- For expenses imported from MyExpense:
  - Expense Description
- For expenses created from receipts:
  - Expense Description
  - Merchant
  - Other details are populated for you, please review if they make sense

There are validation checks in place to make sure the data is correct. If anything is
incorrect, you will see them highlighted in red, otherwise, green. Make sure everything
is green before proceeding to the next step.

### Step 4: Export back to MyExpense

Follow the instructions in the last step of the web interface to export the matched
expenses back to MyExpense. The app will automatically fill in the expense report in
MyExpense for you.

### Step 5: Submit your expense report in MyExpense

You've made it! Now, go back to the MyExpense page, review the filled-in expense
report, and submit it.

### Troubleshooting

#### App Won't Start

- **macOS**: If you see "App can't be opened", right-click → Open, then click "Open" in the security dialog
- **Windows**: If Windows Defender blocks it, click "More info" → "Run anyway"
- **All platforms**: Make sure you have at least 4GB of RAM available

#### App starts, but closes immediately, or run into porting issue

You likely have something already running on the port numbers set in the `.env` file (the defaults are 5001 and 9222). Please free them up by:

- Windows:

```cmd
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":5001 :9222"') do taskkill /PID %a /F
```

- macOS/Linux:

```bash
uv run -m lsof -ti:5001,9222 | xargs kill -9
```

#### API Errors

- Make sure your `.env` file has valid configuration
- Check your internet connection (if using AI features)
- Verify your Azure OpenAI credits/quotas (if using AI features)
- The app can work without API keys for basic functionality

### Getting Help

If you encounter issues:

1. Check the 2 log files (`ez-expense.log` and `ez-expense-fe.log`) in the same folder
   as the executable for error messages. Including these logs when asking for help will
   speed up the troubleshooting process.
2. Ensure your `.env` file is properly configured
3. Try restarting the application

---

**Technical Note**: This app runs a local web server and browser automation. It's completely private - no data leaves your computer except for optional API calls to Azure OpenAI for AI-powered processing.
