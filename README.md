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

## Demo

See the tool in action by clicking on the image below:

👇👇👇👇👇🎥🎥🎥🎥🎥🎥👇👇👇👇👇

<a href="https://microsoft-my.sharepoint-df.com/:v:/p/vuquy/cQr5JCDrsq-sSYttecQmW0udEgUC0Lf9VrdlyBKq5jld8RURVg?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0=&">
  <img src="assets/video_thumbnail.png" alt="Product Demo Video" width="400">
</a>

## Installation

### Recommended way

TIP: You can ask Copilot to do it for you by giving it the link to this repo and asking it to set up the project.

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

### For non-technical users without python

#### ⚠️ No longer actively maintained ⚠️

As noted at the beginning, we now have ClawPilot which truly requires zero setup. While the app releases for this expense tool are available and tested, developing an app that works on every machine is a difficult problem, and as a data scientist, I don't have the motivation nor bandwith to help with all the edge cases.

That being said, the tool still works well, especially if you follow [the instructions to set it up with Python](#installation). The tool has a finetuned user experience, a battle-tested workflows and it's still used by many people.

Therefore, if you have trouble running the app, I highly recommend switching to MSFT's ClawPilot which lets you get started quickly, as the cost of controllability, stability and accuracy.

#### 📥 Download and use

1. Go to [Releases](https://github.com/xquyvu/ez-expense/releases)
2. Download the latest ZIP corresponding to your platform. This contains the executable file and all necessary dependencies.
3. Extract the ZIP file
4. Fill in the content of the `.env.template` file, and rename it to `.env`
   - Configure `DATE_FORMAT` for your region (DD/MM/YYYY or MM/DD/YYYY)
   - (Optional) Set your Azure OpenAI configuration for faster, more accurate extraction

Refer to the [USER GUIDE](deployment/USER_GUIDE.md) for instructions on how to use the app, and common issues.

##### For MacOS

This app is not code-signed (requires $99/year Apple Developer Account). macOS will show a security warning when you first try to open it.

To bypass this, **right-click** `EZ-Expense.app` **→ Open → Open**. macOS will remember your choice and the app will open normally from then on.

If that doesn't work, run this in Terminal:

```bash
/usr/bin/xattr -cr <path_to_your_extracted_package>/EZ-Expense.app
/usr/bin/xattr -cr <path_to_your_extracted_package>/ez-expense
```

##### For Windows

When you launch the app, a prompt will pop up asking for permission. Just allow it, and the app will open normally from then on.

## AI Extraction Options

The app supports three AI providers for extracting invoice details from receipts (PDF, PNG/JPG/GIF, HEIC and HTML receipts are all supported):

| Provider           | Speed               | Accuracy | Setup                                        |
| ------------------ | ------------------- | -------- | --------------------------------------------- |
| **GitHub Copilot** | Fast (parallel)     | Higher   | None — default, uses your existing Copilot login |
| **Azure AI**       | Fast (parallel)     | Higher   | Requires Azure OpenAI config in `.env`        |
| **Local AI**        | Slower (sequential) | Good     | No setup — download model on first use        |

- **GitHub Copilot** is the default: zero setup, just requires you to be signed in to Copilot.
- **Azure AI** is an alternative if you have access to Azure OpenAI. Set `EXTRACTION_PROVIDER=azure`, plus `AZURE_TENANT_ID`, `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` in your `.env` file.
- **Local AI** works offline with no API keys. Just click "Download" in the app to get the model (~400 MB).

### Using GitHub Copilot (fastest way to start)

Nothing to install — the Copilot CLI ships inside the `github-copilot-sdk` dependency
that `uv sync` already installed. Requirements:

1. A GitHub account with an active Copilot subscription (Individual, Business or Enterprise).
2. Sign in once: open the app, go to the **AI Extraction Options** panel, and click
   **Login** next to GitHub Copilot (runs the standard OAuth device-code flow in a
   popup — no terminal needed). The login is cached, so this is a one-time step.

That's it — select the GitHub Copilot radio button and start uploading receipts.

The app also auto-itemizes hotel line items (subcategory, dates, daily rate, quantity) instead of requiring you to fill in the itemization dialog by hand.

## TODO

Not actively maintained, but here are some ideas for future improvements:

- Use another name for .env.template, like openai_config.json
- Instructions to set up Azure OpenAI, create subscription etc.
- Add one-shot mode
- Tidy up the repo
