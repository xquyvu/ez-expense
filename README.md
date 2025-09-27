# Easy expense

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

## 📥 Installation

### Option 1: Direct Download (Recommended)

1. Go to [Releases](https://github.com/xquyvu/ez-expense/releases)
2. Download the latest `ez-expense-macos.zip`
3. Extract the ZIP file
4. Fill in the content of the `.env.template` file, and rename it to `.env`

### Option 2: Homebrew (Power Users)

```bash
# Add the tap and install
brew tap xquyvu/ez-expense
brew install --cask ez-expense
```

### Option 3: Remove Quarantine (Advanced)

```bash
# After installing the app:
xattr -cr /Applications/EZ-Expense.app # Replace this with the path to where you extracted the zip file
```

### ⚠️ Security Notice

This app is not code-signed (requires $99/year Apple Developer Account).
macOS will show a security warning, but you can safely bypass it using the methods above.

## Demo

See the tool in action by clicking on the image below:

👇👇👇👇👇🎥🎥🎥🎥🎥🎥👇👇👇👇👇

<a href="https://microsofteur-my.sharepoint.com/:v:/g/personal/vuquy_microsoft_com/EfkkIOuyr6xJi215xCZbS50BkEFFnWr2-sugqljIYg7-Ow?e=G6FzfQ">
  <img src="assets/video_thumbnail.png" alt="Product Demo Video" width="400">
</a>

## Download and use

Go to the [Releases](https://github.com/xquyvu/ez-expense/releases) page to download the latest version for your OS. This contains the executable file and all necessary dependencies.

Refer to the [USER GUIDE](deployment/USER_GUIDE.md) for instructions on how to use the app.

**IMPORTANT:** You will need to provide your OpenAI API key to the app. Follow the instructions in the User Guide to set it up.

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

- Find other ports if the current ones are not available
- Add one-shot mode
- Tidy up the repo
- Test on Linux
- Check if the tests are still valid
