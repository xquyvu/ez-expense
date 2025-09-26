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

## Demo

See the tool in action!

[🎥 **Watch the Product Demo Video** 📺](assets/Product%20demo.mp4)

*Click the link above to download and watch the demo video showing the tool in action.*

## Download and use

Go to the [Releases](https://github.com/xquyvu/ez-expense/releases) page to download the latest version for your OS. This contains the executable file and all necessary dependencies.

Refer to the [USER GUIDE](deployment/USER_GUIDE.md) for instructions on how to use the app.

**IMPORTANT:** You will need to provide your OpenAI API key to the app. Follow the instructions in the User Guide to set it up.

## Installation for development

```bash
uvx playwright install chromium --with-deps --no-shell
uv sync
```

## TODO

- Add one-shot mode
- Tidy up the repo
- Test on Linux
- Check if the tests are still valid
