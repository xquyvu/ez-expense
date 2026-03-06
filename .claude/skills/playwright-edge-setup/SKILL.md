---
name: playwright-edge-setup
description: Reference for configuring Playwright MCP to use Microsoft Edge instead of Chrome. Use when troubleshooting browser errors or reconfiguring the MCP server.
user-invocable: false
---

# Playwright MCP Edge Configuration

## The problem

Claude Code's Playwright MCP defaults to Chrome. This project requires Microsoft Edge.
The `/mcp` command writes config to `~/.claude.json` without `--browser msedge`,
causing `Chromium distribution 'chrome' is not found` errors.

## Where the config lives

Claude Code reads per-project MCP server configs from **`~/.claude.json`**, NOT from
`~/.claude/settings.json`. The `/mcp` command writes to `~/.claude.json`.

The relevant section is at: `projects > "C:/Users/vuquy/code/ez-expense" > mcpServers`

## Correct config

In `~/.claude.json`, the `playwright` entry must include `--browser msedge`:

```json
"mcpServers": {
  "playwright": {
    "type": "stdio",
    "command": "cmd",
    "args": ["/c", "npx", "-y", "@playwright/mcp@latest", "--browser", "msedge"]
  }
}
```

## After reinstalling via `/mcp`

If you remove and re-add the Playwright MCP via `/mcp`, the `--browser msedge` args
will be lost. Manually edit `~/.claude.json` and add `"--browser", "msedge"` to the
end of the `args` array.

## VS Code MCP config

VS Code has its own MCP config at `%APPDATA%/Code/User/mcp.json`. Keep it consistent:

```json
{
  "servers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--browser", "msedge"]
    }
  }
}
```

## Future fix

The `PLAYWRIGHT_MCP_BROWSER` env var is documented on GitHub but not yet released
in `@playwright/mcp` (as of v0.0.68). Once available, the config can use an `env` field instead.
