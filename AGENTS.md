# Financial Agent — Repository Instructions

## GitHub synchronization

After completing any user-requested modification in this repository:

1. Review the exact Git diff and stage only files that belong to the request.
2. Run the relevant checks or tests for the modified code.
3. Audit the staged content for secrets and private financial data.
4. Commit the completed change with a concise, descriptive message.
5. Push the commit to the configured GitHub remote. When repository policy requires a branch or pull request, push that branch and open or update the pull request.
6. Report the branch, commit, validation result, and GitHub destination to the user.

Never push `.env`, credentials, API keys, Telegram tokens or identifiers, broker exports, holdings, balances, transactions, Investor OS financial records, full Trading Coach reports, local databases, charts, virtual environments, or local tooling. The only generated-report exception is `MARKET_SUMMARY_HISTORY.md`, which may contain the concise, sanitized user-facing daily and Sunday market summaries. If prohibited content appears in the staged diff, stop the publish step, remove it from the Git index without deleting the local files, and report the issue.

## Market-summary archive

- `MARKET_SUMMARY_HISTORY.md` is append-only. Add each final user-facing market summary exactly once under an ISO-dated heading; do not rewrite prior entries during routine runs.
- Before every archive commit, verify UTF-8, prevent duplicate dates, and confirm the staged diff contains only the public summary and no private financial or authentication data.
- Automated archive runs publish directly on `main`. Before appending, require a clean tracked worktree, fetch `origin`, switch to `main`, and fast-forward only from `origin/main`. If this cannot be done safely, do not reset, overwrite, or force the repository; preserve the prepared summary outside Git and report the blocker.
- On synchronized `main`, stage only `MARKET_SUMMARY_HISTORY.md`, commit as `Archive market summary YYYY-MM-DD`, push `main` to `origin`, and verify local `main` equals `origin/main`. Never force-push. Preserve a safe local entry or commit and report the failure if publishing is blocked.
- The parent workspace `AGENTS.md` is authoritative for the current report cadence, content, and length.

## Report contract

- Weekday market news stays short and Telegram-friendly: no more than 2,000 characters and three material headlines.
- Every Sunday, generate two English outputs from the same evidence: a deep professional macro report for the Trading Coach Agent and a concise Telegram executive summary for the user.
- The coach report follows the evidence discipline and analytical architecture defined in the parent workspace `AGENTS.md` and modeled on `AI-Advisor-Build-Guide.pdf`; normally target 3,000-5,000 words.
- The user's summary must follow the parent workspace's compact regime / key moves / bullish / caution / next week / one-sentence structure, target 350-500 words, and stay below 3,800 characters.
- Both weekly outputs must use dated source evidence, distinguish facts from inference and headline claims, state missing evidence, and include confirmation/invalidation conditions. Never invent data to complete a section.
- Save both outputs locally. Copy the full report to the Trading Coach Agent workspace as `Weekly_Macro_Report.md` and the dated Investor OS portfolio record as `Investor_OS_Portfolio_Snapshot.md`. These are context handoffs, not substitutes for Aura's trading ledger, user confirmation, or fresh market data. Send only the concise summary to the user's Telegram.

If authentication, validation, merge conflicts, remote policy, or network access blocks the push, do not bypass the safeguard. Preserve the local commit when safe and tell the user exactly what remains.
