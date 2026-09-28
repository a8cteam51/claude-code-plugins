# Maintenance — syncing with claude-code-plugins

This repo is developed standalone, then mirrored into
`a8cteam51/claude-code-plugins` at `plugins/sp-site-design-harness/` via
`git subtree`, alongside `plugins/html-to-block-theme/`.

## Where things live

- **This repo** (`sp-site-design-harness`) — the source of truth for day-to-day
  development. Commit here normally; nothing about that changes.
- **`claude-code-plugins` clone** — kept at
  `/Users/allancole/Claude Projects/claude-code-plugins`, a sibling folder to
  this one. It exists solely to run subtree syncs and open PRs from; it is not
  where original edits should be made.

## Convention

All real edits to this plugin happen in **this** repo. The copy under
`plugins/sp-site-design-harness/` in `claude-code-plugins` is a mirror. If a
reviewer or coworker ever edits that path directly (e.g. a suggested change
pushed straight to a PR branch), the sync procedure below pulls it back in so
this repo stays the complete history — but the convention to aim for is: real
edits originate here.

## Sync procedure

Triggered whenever asked to "push this to the remote repo." Not automatic on
every commit — a deliberate, periodic action.

1. Update the clone from `origin`:
   ```
   cd "/Users/allancole/Claude Projects/claude-code-plugins"
   git checkout trunk && git fetch origin && git pull origin trunk
   ```
2. Pull any remote-only changes back into this repo (protects against drift):
   ```
   git subtree push --prefix=plugins/sp-site-design-harness \
     "/Users/allancole/Claude Projects/sp-site-design-harness" incoming-sync
   cd "/Users/allancole/Claude Projects/sp-site-design-harness"
   git log incoming-sync ^main --oneline   # check what's new, if anything
   git merge incoming-sync                  # only if there's something new
   git branch -d incoming-sync
   ```
3. Push this repo's new commits up via a fresh sync branch:
   ```
   cd "/Users/allancole/Claude Projects/claude-code-plugins"
   git checkout -b sync-sp-site-design-harness-<date> trunk
   git subtree pull --prefix=plugins/sp-site-design-harness \
     "/Users/allancole/Claude Projects/sp-site-design-harness" main \
     -m "Sync sp-site-design-harness updates"
   git push -u origin sync-sp-site-design-harness-<date>
   gh pr create --title "Sync sp-site-design-harness updates" --body "..."
   ```
4. Report the PR link. Do not merge or enable auto-merge unless explicitly
   asked — this repo is shared with a coworker.

## Requirements

- The `claude-code-plugins` clone must keep existing at the path above; each
  sync pulls into/pushes from it rather than a fresh clone.
- No fork needed — push access to `a8cteam51/claude-code-plugins` is direct.
