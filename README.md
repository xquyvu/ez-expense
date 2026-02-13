# Hyper Velocity Expense

Get your expenses done in just a few clicks (using AI of course).

## Introduction

Doing the expenses is boring and painful.

For every expense item, you need to identify the matching receipt files, whose names
very often do not indicate what they are about. Then, uploads the the receipts one at a
time, filling in details on a tool that is slow, unresponsive, and error prone.

What if you could just, give the receipts to someone and say "Go figure it out"?

This tool lets you do exactly just that. It uses AI and automation to parse the
receipts, match them to the correct expense lines, then go and fill in the expense
report without you needing to do a single thing.

Just click the app, and it just works. No installation required, no coding involve.

## 📥 Download and use

1. Go to [Releases](https://github.com/xquyvu/ez-expense/releases)
2. Download the latest ZIP corresponding to your platform. This contains the executable file and all necessary dependencies.
3. Extract the ZIP file
4. Fill in the content of the `.env.template` file, and rename it to `.env`
   - Configure `DATE_FORMAT` for your region (DD/MM/YYYY or MM/DD/YYYY)
   - (Optional) Set your Azure OpenAI configuration for faster, more accurate extraction

Refer to the [USER GUIDE](deployment/USER_GUIDE.md) for instructions on how to use the app, and common issues.

### AI Extraction Options

The app supports two AI providers for extracting invoice details from receipts:

| Provider     | Speed               | Accuracy | Setup                                  |
| ------------ | ------------------- | -------- | -------------------------------------- |
| **Azure AI** | Fast (parallel)     | Higher   | Requires Azure OpenAI config in `.env` |
| **Local AI** | Slower (sequential) | Good     | No setup — download model on first use |

- **Azure AI** is recommended if you have access to Azure OpenAI. Set `AZURE_OPENAI_ENDPOINT` and `INVOICE_DETAILS_EXTRACTOR_MODEL_NAME` in your `.env` file.
- **Local AI** works offline with no API keys. Just click "Download" in the app to get the model (~400 MB).

### For MacOS

This app is not code-signed (requires $99/year Apple Developer Account). macOS will show a security warning when you first try to open it.

To bypass this, **right-click** `EZ-Expense.app` **→ Open → Open**. macOS will remember your choice and the app will open normally from then on.

If that doesn't work, run this in Terminal:

```bash
/usr/bin/xattr -cr <path_to_your_extracted_package>/EZ-Expense.app
/usr/bin/xattr -cr <path_to_your_extracted_package>/ez-expense
```

## Demo

See the tool in action by clicking on the image below:

👇👇👇👇👇🎥🎥🎥🎥🎥🎥👇👇👇👇👇

<a href="https://microsoft-my.sharepoint-df.com/:v:/p/vuquy/cQr5JCDrsq-sSYttecQmW0udEgUC0Lf9VrdlyBKq5jld8RURVg?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0=&">
  <img src="assets/video_thumbnail.png" alt="Product Demo Video" width="400">
</a>

## Installation and run for development

```bash
git clone https://github.com/xquyvu/ez-expense.git
cd ez-expense
uvx playwright install chromium --with-deps --no-shell
uv sync
```

Then, modify your `.env` file as per the instructions in `deployment/USER_GUIDE.md`.

Run the app:

```bash
uv run python main.py
```

## TODO

- Use another name for .env.template, like openai_config.json
- Instructions to set up Azure OpenAI, create subscription etc.
- Improve UX for people without AzureOpenAI / subscription etc.
- Find other ports if the current ones are not available
- Make names consistent (HVE, EZ-Expense, Hyper Velocity Expense)
- Add one-shot mode
- Tidy up the repo
