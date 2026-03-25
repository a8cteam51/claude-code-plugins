# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is **a8cteam51-claude-code-plugins** — Claude Code plugins built by Automattic's Special Projects team (Automattic Special Projects) for WordPress development, security, and client work.

Automattic Special Projects helps interesting people, projects, and organizations have an excellent experience with WordPress. These plugins support that mission by automating common workflows.

## Architecture

### Plugin Structure

```text
a8cteam51-claude-code-plugins/
├── .claude-plugin/
│   └── marketplace.json          # Plugin registry
├── plugins/
│   └── plugin-name/
│       ├── CHANGELOG.md           # Version history
│       ├── skills/                # Skills with SKILL.md files
│       │   └── skill-name/
│       │       └── SKILL.md
│       ├── commands/              # Slash commands (optional)
│       │   └── command.md
│       └── scripts/               # Helper scripts (optional)
└── CLAUDE.md                      # This file
```

### Skills Specification

All skills must have a `SKILL.md` file with YAML frontmatter:

- **Required frontmatter fields**:
  - `name` - hyphen-case, lowercase alphanumeric + hyphens
  - `description` - when Claude should use this skill
- **Optional frontmatter fields**:
  - `license`
  - `metadata` - custom key-value pairs
- **Body**: Markdown instructions, examples, and guidelines

## Using This Marketplace

### Adding to Claude Code

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
```

### Installing Plugins

```bash
# Browse available plugins
/plugin

# Install specific plugin
/plugin install <plugin-name>@a8cteam51-claude-code-plugins
```

## Creating New Plugins

1. **Create plugin directory** under `plugins/`:

   ```bash
   mkdir -p plugins/my-plugin/{skills,commands,scripts}
   ```

2. **Add CHANGELOG.md**:

   ```markdown
   # Changelog

   ## [1.0.0] - YYYY-MM-DD

   ### Added
   - Initial release
   ```

3. **Create skills/commands** as needed

4. **Register in marketplace.json**:

   ```json
   {
     "name": "my-plugin",
     "source": "./plugins/my-plugin",
     "description": "Plugin description",
     "version": "1.0.0",
     "author": { "name": "Automattic Special Projects" },
     "repository": "https://github.com/a8cteam51/claude-code-plugins",
     "license": "MIT",
     "keywords": ["keyword1", "keyword2"],
     "category": "development-tools",
     "strict": true,
     "skills": ["./skills/my-skill"]
   }
   ```

## Versioning & Releases

### Plugin-Prefixed Tags

Since this repository contains multiple plugins with independent version cycles, use **plugin-prefixed tags**:

**Tag Format:** `<plugin-name>/v<semver>`

**Examples:**
- `plugin-review/v1.0.0`

### Release Process

1. Update `CHANGELOG.md` in the plugin directory
2. Update version in `.claude-plugin/marketplace.json`
3. Commit with conventional commit format: `feat: description vX.Y.Z`
4. Tag: `git tag <plugin-name>/vX.Y.Z && git push --tags`
5. Create GitHub release: `gh release create <plugin-name>/vX.Y.Z --title "<plugin-name> vX.Y.Z"`

## License

MIT License - See LICENSE file for details.
