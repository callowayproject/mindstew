# mindstew

A native macOS app that builds a personal wiki from documents and lets a local chat agent work over it.

## Language

**Skill**:
A folder containing a `SKILL.md` (YAML frontmatter with `name` and `description`, plus Markdown instructions) that the chat agent can be told to follow.
_Avoid_: plugin, command, prompt template

**Skill source**:
A directory root scanned for Skills: the global one in Application Support, or the vault-local one under `.mindstew/skills/`. A vault-local Skill shadows a global Skill of the same name.
_Avoid_: skill library, skill repo

**Vault archive**:
A single file produced by Export Project that Import Project can turn back into a vault.
_Avoid_: backup, bundle, package

**Derived data**:
Anything under `.mindstew/index/` or `.mindstew/cache/` that can be rebuilt from `sources/` and `wiki/`.
_Avoid_: cache, index files

**Portable state**:
The non-derivable part of a vault's ingest state (review flags and image caption records) that travels inside a Vault archive.
_Avoid_: ingest state, database export
