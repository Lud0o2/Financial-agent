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

If authentication, validation, merge conflicts, remote policy, or network access blocks the push, do not bypass the safeguard. Preserve the local commit when safe and tell the user exactly what remains.
