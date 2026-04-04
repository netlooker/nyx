---
name: github
description: Interact with GitHub repos, PRs, issues, and releases via the gh CLI.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["gh"]}}}
---

# GitHub CLI

`gh` is pre-installed and auth persists across container rebuilds via `/data/gh`.

## First-time auth

If `gh auth status` shows no active account, authenticate:

```bash
gh auth login
```

Choose HTTPS + browser or paste a personal access token. The token is stored in `/data/gh/` and survives rebuilds.

## Cloning repos

Always clone into the workspace `projects/` directory:

```bash
cd /data/workspace/projects
gh repo clone owner/repo
```

## Common operations

### Pull requests

```bash
# Create PR from current branch
gh pr create --title "title" --body "description"

# List open PRs
gh pr list

# View PR details and checks
gh pr view 123
gh pr checks 123

# Review and merge
gh pr review 123 --approve
gh pr merge 123 --squash
```

### Issues

```bash
# List issues
gh issue list
gh issue list --label bug --state open

# Create issue
gh issue create --title "title" --body "description" --label bug

# View and comment
gh issue view 42
gh issue comment 42 --body "update here"
```

### Releases

```bash
# List releases
gh release list

# Create release from tag
gh release create v1.0.0 --title "v1.0.0" --generate-notes
```

### API calls

For anything not covered by built-in commands, use the API directly:

```bash
# Get PR comments
gh api repos/owner/repo/pulls/123/comments

# Get workflow runs
gh api repos/owner/repo/actions/runs --jq '.workflow_runs[:5] | .[].conclusion'

# GraphQL
gh api graphql -f query='{ viewer { login } }'
```

## Repo context

`gh` commands are context-aware — run them from inside a cloned repo and they target that repo automatically. Outside a repo, specify `--repo owner/repo` or `-R owner/repo`.

## Auth persistence

| Path | Purpose |
|------|---------|
| `/data/gh/` | Token storage, persists across rebuilds |
| `GH_CONFIG_DIR=/data/gh` | Set in Dockerfile, no symlinks needed |

Auth survives container rebuilds. It does **not** survive volume wipes.
