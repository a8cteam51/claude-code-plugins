---
description: Address unresolved PR review comments. Pass the GitHub PR URL as the argument (e.g. /pr-addr-feedback https://github.com/org/repo/pull/123). Uses gh CLI for auth — works with private repos.
allowed-tools: Bash(gh api:*), Bash(gh pr view:*), Read, Edit, AskUserQuestion
---

You are helping the user address unresolved review comments on a GitHub pull request. The PR URL is: `$ARGUMENTS`

## Step 1: Parse the PR URL

Extract `owner`, `repo`, and `pull_number` from the URL. The URL format is:
`https://github.com/{owner}/{repo}/pull/{pull_number}`

## Step 2: Fetch unresolved review threads

Use the GitHub GraphQL API via `gh api graphql` to fetch all unresolved threads and their comments:

```bash
gh api graphql -f query='
{
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PULL_NUMBER) {
      title
      headRefName
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 10) {
            nodes {
              body
              path
              line
              originalLine
              diffHunk
              author { login }
              url
              createdAt
            }
          }
        }
      }
    }
  }
}'
```

Filter to threads where `isResolved` is `false` and `isOutdated` is `false`. If there are no unresolved threads, tell the user and stop.

## Step 3: Show a summary

Before doing anything, print a brief summary:
- PR title and branch
- Number of unresolved threads found
- List of files touched by comments

Then proceed without asking for confirmation.

## Step 4: Process each thread

For each unresolved thread, work through the following logic. Process them one at a time, in order.

### 4a: Read context

Use the `Read` tool to open the file at `path`. Focus on the lines referenced in `line` or `originalLine`, plus ~15 lines of surrounding context.

Also look at `diffHunk` from the comment — it shows the exact diff context the reviewer saw.

### 4b: Evaluate validity

Assess whether the feedback is valid. Consider:
- Is the suggested change technically correct?
- Does it improve clarity, correctness, performance, or security?
- Is it a matter of style/preference with no clear right answer?
- Does the comment contradict the existing codebase patterns?
- Is the comment outdated (e.g., refers to code that no longer exists)?

### 4c: Branch on verdict

**If the feedback is VALID** (clear improvement): Address it directly using the `Edit` tool. Make the minimal change needed to satisfy the comment. Do not refactor beyond what was requested.

**If the feedback is QUESTIONABLE or INVALID** (style preference, unclear, contradicts codebase patterns, or you're unsure): Use `AskUserQuestion` to surface it to the user before acting. Show:
- The reviewer's comment
- The relevant code snippet
- Your reasoning for why it may not be valid
- Two options: "Address it anyway" or "Skip this one"

## Step 5: Final summary

After all threads are processed, print a summary table:

```
## PR Feedback Summary

| # | File | Reviewer | Status | Action |
|---|------|----------|--------|--------|
| 1 | src/foo.php:42 | copilot | ✅ Valid | Fixed |
| 2 | src/bar.php:17 | human   | ⚠️ Skipped | User chose to skip |
| 3 | src/baz.php:88 | coderabbit | ✅ Valid | Fixed |
```

Do not post any comments to GitHub. Do not resolve threads on GitHub. The user will handle that in their own workflow.

## Important notes

- Never make changes outside the files referenced in review comments.
- Do not run `git commit`, `git push`, or any git commands.
- Prefer the smallest valid fix — do not improve surrounding code not mentioned in the comment.
- If a comment thread has multiple replies, read all of them to understand the full context before acting.
- If the file referenced in a comment no longer exists at that path, skip the thread and note it in the summary.
