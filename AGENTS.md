# Financial Agent — Repository Instructions

## GitHub synchronization

After completing any user-requested modification in this repository:

1. Review the exact Git diff and stage only files that belong to the request.
2. Run the relevant checks or tests for the modified code.
3. Audit the staged content for secrets and private financial data.
4. Commit the completed change with a concise, descriptive message.
5. Push the commit to the configured GitHub remote. When repository policy requires a branch or pull request, push that branch and open or update the pull request.
6. Report the branch, commit, validation result, and GitHub destination to the user.

Never push `.env`, credentials, API keys, Telegram tokens, broker exports, holdings, balances, transactions, Investor OS financial records, generated briefs, local databases, charts, virtual environments, or local tooling. If any of these appear in the staged diff, stop the publish step, remove them from the Git index without deleting the local files, and report the issue.

## Report contract

- Weekday market news stays short and Telegram-friendly: no more than 2,000 characters and three material headlines.
- Every Sunday, generate two English outputs from the same evidence: a deep professional macro report for the Trading Coach Agent and a concise Telegram executive summary for the user.
- The coach report follows the evidence discipline and analytical architecture defined in the parent workspace `AGENTS.md` and modeled on `AI-Advisor-Build-Guide.pdf`; normally target 3,000-5,000 words.
- The user's summary must follow the parent workspace's compact regime / key moves / bullish / caution / next week / one-sentence structure, target 350-500 words, and stay below 3,800 characters.
- Both weekly outputs must use dated source evidence, distinguish facts from inference and headline claims, state missing evidence, and include confirmation/invalidation conditions. Never invent data to complete a section.
- Save both outputs locally. Copy the full report to the Trading Coach Agent workspace as `Weekly_Macro_Report.md` and the dated Investor OS portfolio record as `Investor_OS_Portfolio_Snapshot.md`. These are context handoffs, not substitutes for Aura's trading ledger, user confirmation, or fresh market data. Send only the concise summary to the user's Telegram.

If authentication, validation, merge conflicts, remote policy, or network access blocks the push, do not bypass the safeguard. Preserve the local commit when safe and tell the user exactly what remains.
