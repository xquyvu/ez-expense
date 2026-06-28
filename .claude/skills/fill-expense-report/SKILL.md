---
name: fill-expense-report
description: "End-to-end fill of a MyExpense report using the local ez-expense app (the Quart web UI in /Users/quyvu/code/ez-expense). The user has the app running and has navigated MyExpense to the target report; the agent then drives the ez-expense web UI via the Playwright MCP to import expenses, bulk-upload receipts from a folder, auto-match them, run hotel itemization, and fill the report. Trigger whenever the user asks to 'fill an expense report end-to-end with the ez-expense app', 'use the ez-expense FE to fill receipts', or any phrasing that combines a receipts folder + the ez-expense FE app."
---

# /fill-expense-report — Drive the local ez-expense app end-to-end

This skill drives the local **ez-expense** Quart web app. Use this when the user wants the agent to click through its web UI for them.

## Architecture (read this once)

Two independent browsers are in play:
1. **Edge (port 9222)** — opened by `main.py`; this is where MyExpense lives. The user navigates this browser to the target expense report. The ez-expense backend drives it via Playwright (CDP).
2. **Playwright MCP browser** — the agent's own browser, used only to click around the ez-expense web UI at `http://127.0.0.1:5001`.

The agent never directly clicks in MyExpense. Every action goes: agent → MCP browser → ez-expense web UI → ez-expense backend → MyExpense (Edge).

## Step 1: Confirm preconditions

Before driving anything, verify:
1. The app is started via `main.py` (NOT just `front_end/app.py`). `main.py` launches the Edge debug browser at port 9222 _and_ the FE web server. `front_end/app.py` alone gives you a server with no backend MyExpense session and every fill call will return "Browser session not available".
2. The `.env` file at the repo root sets `IMPORT_EXPENSE_MOCK=False`. Mock mode imports 11 fake CHF expenses from `sandbox/` and silently bypasses MyExpense — every test will look "correct" but never touch the actual report.
3. `lsof -iTCP:5001` (FE) and `lsof -iTCP:9222` (Edge debug) both show a listener.
4. The user has signed in to MyExpense in the Edge window and **navigated to the target expense report** (not just the workspace landing page).
5. The receipts folder is known and accessible.

Start the stack with:
```bash
cd "<path_to_ez_expense>"
nohup uv run python main.py > /tmp/ez-main.log 2>&1 &
```

Wait ~15 seconds for Edge to launch + Quart to bind to port 5001.

If any precondition is missing, ask and stop.

## Step 2: Inventory the receipts folder

`ls -la "<path_to_receipts>"` and ask the user to confirm:
- Which files belong to this report (skip personal/duplicate files outside the date range).
- For any **single physical receipt that covers multiple expense lines** (e.g. a transit pass with 7×$3 rides; an Uber split into 81 + 2), require duplicated copies — one per line — and confirm filenames. The ez-expense matcher attaches one file per expense line, so without copies, only one line gets the receipt.
- HEIC/HEIF photos are converted server-side; they're fine to include.

## Step 3: Drive the FE — import expenses

Using the Playwright MCP browser:

```
playwright-browser_navigate http://127.0.0.1:5001/
# Tick the "I've navigated to the expense report" checkbox
playwright-browser_evaluate "() => document.getElementById('navigation-checkbox').click()"
# Click Import
playwright-browser_evaluate "() => document.getElementById('import-from-website-btn').click()"
# Wait for the expense table to appear
playwright-browser_wait_for "Add Row"
```

Take a screenshot, confirm the imported rows match the user's report.

## Step 4: Upload receipts

The Bulk Receipt Upload Area takes files via a hidden `<input type="file" id="bulk-receipt-input">`. Triggering the file chooser requires opening the OS file dialog first — Playwright's MCP can then attach files via the active modal:

```
// 1. Open the file chooser (this triggers the OS dialog, which the MCP intercepts)
playwright-browser_evaluate "() => app.selectBulkReceipts()"
// 2. Immediately attach files
playwright-browser_file_upload paths=[ <absolute paths to each receipt> ]
```

**Critical: file-path constraint.** The Playwright MCP only accepts file paths **inside its allowed roots** (typically the repo root + `.playwright-mcp/`). Files in `/Users/<user>/Desktop/...` will be rejected with `File access denied: ... is outside allowed roots`. Workaround: copy the user's receipts into a project-local folder first (e.g. `/Users/quyvu/code/ez-expense/.session-receipts/`), upload from there, and clean up at the end.

```bash
mkdir -p "<path_to_ez_expense>/.session-receipts"
cp "<path_to_receipts>/*.pdf"  "<path_to_ez_expense>/.session-receipts/"
cp "<path_to_receipts>/*.heic" "<path_to_ez_expense>/.session-receipts/"
cp "<path_to_receipts>/*.html" "<path_to_ez_expense>/.session-receipts/"
```

After upload, poll for AI extraction to finish:

```js
() => ({
  bulkCount: app.bulkReceipts?.length || 0,
  extracted: app.bulkReceipts?.filter(r => r.invoiceDetails)?.length || 0,
  failed: app.bulkReceipts?.filter(r => r.extractionFailed)?.length || 0,
  loadingText: document.getElementById('loading-text')?.textContent
})
```

With Copilot AI enabled, extraction is parallel and typically takes <1 min for 25 receipts.

## Step 5: Match receipts → expenses

Click **Match receipts with expenses** — `app.matchReceiptsWithExpenses()`. The matcher attaches one receipt per expense line based on amount/date/merchant proximity.

**Diagnose what's left unmatched:**

```js
() => {
  const unmatchedExpenses = app.expenses
    .filter(e => (app.receipts.get(e.id) || []).length === 0)
    .map(e => ({id: e.id, amount: e.Amount, currency: e.Currency, merchant: e.Merchant, date: e.Date}));
  const unmatchedReceipts = (app.bulkReceipts || []).map(r => ({
    name: r.name,
    amount: r.invoiceDetails?.Amount,
    currency: r.invoiceDetails?.Currency,
    date: r.invoiceDetails?.Date,
    merchant: r.invoiceDetails?.Merchant
  }));
  return { unmatchedExpenses, unmatchedReceipts };
}
```

**Common reasons the matcher leaves something on the table:**
- One physical receipt covers multiple expense lines (e.g. an ORCA transit pass showing a $21 total that's really 7 × $3 individual rides). The receipt's extracted amount won't equal any single expense's amount.
- A single transaction was split across multiple expense lines (e.g. an Uber 83.29 GBP showing up as two separate lines: 81 and 2). The receipt's amount won't equal either line individually.
- Refund / negative-amount expenses (the receipt usually matches the corresponding positive line — usually fine, just verify).

**Manual matching via the JS API** (no drag-and-drop needed — robust against splicing):

```js
async () => {
  // Pairs you want to force-match: [expenseId, exactReceiptFilename]
  // Use one entry per (expense, receipt-copy) pair. If one physical receipt covers
  // multiple expense lines, the user must have duplicated the file before upload so
  // the bulk pool contains N distinct filenames (e.g. "ORCA.pdf", "ORCA 2.pdf", ...).
  // Match strictly by exact filename — never by regex or substring — so you always
  // know which copy went where.
  const pairs = [
    [8,  "ORCA-Contactless-Transaction-History-8359.pdf"],
    [25, "uber-83-29.pdf"],
  ];
  const log = [];
  for (const [expId, filename] of pairs) {
    const idx = app.bulkReceipts.findIndex(r => r.name === filename);
    if (idx === -1) { log.push(`No receipt named "${filename}" left for expense ${expId}`); continue; }
    const receipt = app.bulkReceipts[idx];
    log.push(`Attaching ${receipt.name} -> expense ${expId}`);
    await app.handleReceiptDrop({ sourceType: 'bulk', sourceIndex: idx, receipt }, expId);
  }
  return { log, remaining: app.bulkReceipts.length };
}
```

`app.handleReceiptDrop` is the same function the drag-drop UI calls. It hits `/api/expenses/match-receipt` server-side, attaches the file to the expense, and splices it out of `bulkReceipts`. Looking up the next receipt by **exact filename** each iteration is essential — looking up by stale index breaks after the first splice.

**Always look up by exact `r.name === filename` — never by regex/substring.** This makes the mapping auditable: the user can see exactly which physical receipt copy went onto which expense line, and reordering the `pairs` list doesn't silently change attachments.

After manual matching, verify everything is paired:

```js
() => ({
  matched: app.expenses.filter(e => (app.receipts.get(e.id) || []).length > 0).length,
  total: app.expenses.length,
  bulkRemaining: app.bulkReceipts.length
})
```

Goal: `matched === total` and `bulkRemaining === 0`. If a receipt is genuinely extra (e.g. covers a personal expense not in the report), leaving it in the bulk pile is fine — but flag this to the user before filling.

## Step 6: Itemize hotel expenses

Click **Itemize hotel expenses** — `app.itemization.extract()`. The right pane will show the hotel PDF; the left pane will show extracted line items (Daily Room Rate, taxes, etc.). For each hotel:
1. Cross-check the daily rate × quantity total matches the expense amount (the bottom-of-card footer says "Itemized X matches expense amount Y" in green when balanced).
2. Fix any rows with red validation errors (date must be M/D/YYYY, rate/qty must be positive).
3. Click **Confirm** to lock.

If totals don't reconcile (e.g. a small parking charge missing), add a row manually.

## Step 7: Fill the expense report

Click **Fill Expense Report** — `app.fillExpenseReport()`. This:
1. Streams progress events over SSE while the backend fills each line + uploads its receipt to MyExpense.
2. After the expense fill completes, if itemization was confirmed, runs the itemization fill (clicks into the hotel line, opens the Itemize dialog, fills the rows).

**Polling progress** (use this instead of `playwright-browser_wait_for "Done"` — the FE doesn't put a "done" string anywhere obvious):

```js
() => ({
  overlay: document.getElementById('loading-overlay')?.style?.display,
  text: document.getElementById('loading-text')?.textContent,
  progressBarWidth: document.getElementById('loading-progress-bar')?.style?.width
})
```

Expect to see `Filling expense N/26...` from 1 → 26, then `Filling hotel itemization into MyExpense...`, then overlay hidden.

**Timing.** At ~10–12 s per expense line + receipt upload, expect ~5–7 min for 26 lines. Hotel itemization adds ~30–60 s. Poll every 2–3 min — don't tight-loop.

**Itemization step diagnostics.** The backend `click_itemize_button` now waits for the Dynamics blocking overlay before clicking, retries the Actions menu click up to 3 × across three selectors, falls back to a force-click, and on a Itemize-menuitem timeout dumps the currently visible menu items so you can see *what* Dynamics rendered instead of "Itemize". When debugging a failure:

1. Tail the main.py log for `[itemize]`-prefixed lines:
   ```bash
   grep '\[itemize\]' /tmp/ez-main.log | tail -30
   ```
   Look for which `Actions clicked via …` selector worked, how long `Itemize menuitem found` took, and the `dialog opened in …` total. If the error log shows `Visible buttons/menuitems (top 25): …` you can see whether Dynamics rendered a different menu (e.g. read-only state) and feed the fix back here.

2. Don't blindly re-trigger the fill from the FE — diagnose first. The 26-line fill phase locks the report; spamming `app.itemization.fillIntoMyExpense()` while a previous attempt is mid-retry can cause the "Fill already in progress" 409.

3. If you've confirmed the expense-fill phase finished and the itemization phase legitimately needs a retry (e.g. you fixed a selector and want to verify it works), then:
   ```js
   async () => await app.itemization.fillIntoMyExpense()
   ```
   Look for `{ success: true, results: [{ balanced: true, lines: N, ... }] }`.

## Step 8: Hand off

When fill completes successfully:
- Tell the user the report is ready for review in MyExpense.
- **DO NOT submit on their behalf** — the user always submits themselves.
- Suggest verifying: amounts, categories, that every line has a receipt, that hotel itemization Remaining = 0 in MyExpense.

## Cleanup

After successful fill, only on the user's explicit request:
- Kill the `main.py` process (find PID via `lsof -iTCP:5001 -sTCP:LISTEN`).
- Edge debug window persists (the user can close it).
- If the user asks to "sleep the mac", run `pmset sleepnow` last.

## Failure recovery

- "Browser session not available" → MyExpense Edge tab was closed. Restart `main.py`.
- "Fill already in progress" → an SSE stream is still running. Wait or refresh the FE page.
- Validation errors block fill → fix highlighted cells in the main table, then re-click Fill.
- Itemization unconfirmed → either click Confirm or click Clear to skip itemization.
- **`Could not locate expense line with Created ID …` after partial fill** → the report's grid is virtualised at ~25 rows, so reports with >25 lines (or with leftover orphan itemization rows from a prior fill) can leave the last rows unreachable. The backend now tries (in order) wheel-scroll → keyboard nav (clicks the last visible Created-ID input and presses ArrowDown). For grids where ArrowDown alone doesn't scroll past the rendered window, examine `[fill-debug] locate` log lines to see what's actually rendered. Common cause: itemization sub-rows (Created IDs sharing a batch ID) eating render slots — the importer filters those at import time (`expense_importer._drop_itemization_sub_rows`) and the fill route pre-clears any remaining ones for hotel expenses before the main fill loop.

## Known reliability quirks (learnt the hard way)

- **Hotel itemization re-creates batches on dialog save**: clicking Itemize on a hotel and closing the dialog (even after deleting all rows) **commits whatever rows are still in the dialog under a brand-new itemization batch ID**. Don't bail out of `_clear_existing_itemization_rows` early on a single "row count didn't decrease" sample — wait a longer settle delay (>1 s) and re-check. The current implementation requires 3 consecutive no-progress observations before giving up.
- **`Actions` menu name is ambiguous on the report detail page** — there are TWO Actions buttons (the toolbar one `MoreActions` showing report-level options like "Edit expense report" / "Export to Microsoft Excel", and the per-expense-line `CardBottomMenuFormMenuButtonControl` showing "Attach receipt" / **"Itemize"** etc.). Always prefer the per-line selector first; `get_by_role("button", name="Actions")` matches both and may pick the wrong one.
- **Receipt-upload OK button is intermittently disabled** for ~20-30 seconds after upload finishes. The fill flow's `Page.click: Timeout 30000ms exceeded` against `OkButtonAddNewTabPage` is usually transient — retrying the whole `Fill Expense Report` button picks up where it left off (re-locating already-filled expenses is idempotent).
- **The export from MyExpense includes itemization sub-lines as separate rows**. If a hotel was previously itemized, re-importing produces N+1 rows (parent + N child items, all sharing the same batch CreatedID). `expense_importer._drop_itemization_sub_rows` filters those out at import time by matching their `Expense category` against the `HOTEL_SUBCATEGORIES` list. If a hotel has been "Split" instead of "Itemized" or otherwise locked into a state without an Itemize action, the per-line Actions menu shows "Attach receipt / Edit / Financial dimensions / Split / Split to personal" (no Itemize). Pre-clear logs and skips gracefully.

## Out of scope

- Direct MyExpense automation (see the `expense-report` skill).
- Creating a new expense report in MyExpense — the user must create + navigate to it first.
- Submitting the report.
