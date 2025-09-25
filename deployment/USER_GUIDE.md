# EZ-Expense Standalone Application

EZ-Expense is a tool that helps you automatically match receipts to your expense reports using AI, then fill in the expense report in MyExpense for you.

## How to Use

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

### Step 0: Environment Configuration

The app needs some configuration to work properly. You'll find a `.env.template` file in the same folder as the executable.

**Setup Steps:**

1. **Rename** `.env.template` to `.env`
2. **Edit** the file with your settings:

```bash
# Choose your browser: chrome, edge
BROWSER=edge

# For extraction receipt details with AI (Optional)
# These details can be found in our Azure OpenAI deployment
AZURE_OPENAI_API_KEY=abcdefghi
AZURE_OPENAI_ENDPOINT=https://jklmnopq.openai.azure.com/

# These are reasonable defaults, but you can change them if needed
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
```

### Troubleshooting

#### App Won't Start

- **macOS**: If you see "App can't be opened", right-click → Open, then click "Open" in the security dialog
- **Windows**: If Windows Defender blocks it, click "More info" → "Run anyway"
- **All platforms**: Make sure you have at least 4GB of RAM available

#### API Errors

- Make sure your `.env` file has valid configuration
- Check your internet connection (if using AI features)
- Verify your Azure OpenAI credits/quotas (if using AI features)
- The app can work without API keys for basic functionality

### Getting Help

If you encounter issues:

1. Check the 2 log files (`ez-expense.log` and `ez-expense-fe.log`) in the same folder as the executable for error messages
2. Ensure your `.env` file is properly configured
3. Try restarting the application
4. Check that no other applications are using ports 5001 or 9222. If there is, close them and restart EZ-Expense

### Updates

To update EZ-Expense:

1. Download the new version
2. Replace the old executable with the new one
3. Your data and settings will be preserved

---

**Technical Note**: This app runs a local web server and browser automation. It's completely private - no data leaves your computer except for optional API calls to Azure OpenAI for AI-powered processing.
