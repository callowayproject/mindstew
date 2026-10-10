# Changelog

## 0.3.0 (2026-10-10)

[Compare the full difference.](https://github.com/callowayproject/mindstew/compare/0.2.0...0.3.0)

### Fixes

- Fix: Keep registering the vault in open after the scaffold refactor. [b611ba8](https://github.com/callowayproject/mindstew/commit/b611ba8c1666abe6dede372582f4102a6e49cc0a)

- Fix: Address PR #49 review findings (open fills derived dirs, Link type, cleanups). [d60e7b7](https://github.com/callowayproject/mindstew/commit/d60e7b7b873bb6ccbf6cb3e56a243f89857d0fa6)

- Fix: Warn instead of silently overwriting a corrupt registry on new/open (#36). [bae1404](https://github.com/callowayproject/mindstew/commit/bae140444c1f4fea27979e43da4f9754baf8f5ee)

- Fix: Treat dangling symlinks as scaffold conflicts; update Vault glossary (#33). [e6779cf](https://github.com/callowayproject/mindstew/commit/e6779cf2e5c5fda03006f05a4519ca8a0e8e5e89)

- Fix: Report conflicting entries instead of crashing in open/new (#33). [16cc6f5](https://github.com/callowayproject/mindstew/commit/16cc6f58210192656565cb6132e083574514de56)

- Fix: Keep combining marks, lowercase not casefold, drop fallback extension (#35). [54899fc](https://github.com/callowayproject/mindstew/commit/54899fc65b2d800a50950b69ec4b94d37770b241)

### New

- Add: Machine-global project registry; ls without a path lists projects (#36). [69f63a7](https://github.com/callowayproject/mindstew/commit/69f63a7fbf40126e48849d1c31c24e3a866f424a)

- Add: Non-destructive vault adoption via mindstew open (#33). [57a4d4c](https://github.com/callowayproject/mindstew/commit/57a4d4c7cd7353a139f2ba4f1c6bad81c6f98cc7)

- Add: Filename byte cap and Windows reserved-name handling for slugs (#35). [95b8ac8](https://github.com/callowayproject/mindstew/commit/95b8ac8f206d8777c7de6247909e763301fb7516)

- Add: Page slugs with numeric disambiguation (#35). [72bedcd](https://github.com/callowayproject/mindstew/commit/72bedcd520abc5cf8e18b00fa7e89edfe0c99450)

- Add: Shared wikilink resolver with alias support; show prints link resolution (#34). [6da9bae](https://github.com/callowayproject/mindstew/commit/6da9baeae0884deac101ea12045eeca54843b783)

### Updates

- Update: Bump Python versions in test matrix to 3.13 and 3.14. [a494cef](https://github.com/callowayproject/mindstew/commit/a494cefd516185307eb83ab35aba9c70a0fdbfdb)

- Remove: GitHub Actions workflows for publishing docs and previews. [aaae042](https://github.com/callowayproject/mindstew/commit/aaae042987ae2a6d5bd57fa7db0b11c491259bbb)

- Change: Tighten resolver tests and show link output (#34). [c4caac5](https://github.com/callowayproject/mindstew/commit/c4caac548414b02d1d0fcd5fe398c52b46fdc73e)

## 0.2.0 (2026-10-10)

[Compare the full difference.](https://github.com/callowayproject/mindstew/compare/0.1.0...0.2.0)

### New

- Add: GitHub Actions workflow to build and release Python package. [2b26c1e](https://github.com/callowayproject/mindstew/commit/2b26c1e29e728e09d03b9f2adc520fe94e701f4f)

- Add: Configure detect-secrets pre-commit hook with baseline file. [175f3c3](https://github.com/callowayproject/mindstew/commit/175f3c37195e95d26cb09a4baa5c714d564f9739)

- Add: Page model, tolerant frontmatter reader, ls/show commands (#32). [15178db](https://github.com/callowayproject/mindstew/commit/15178db93cf3a59870603da05dce2f6175a5e1c8)

- Add: Vault scaffold, click CLI skeleton and temp-vault test fixture (#31). [bff357b](https://github.com/callowayproject/mindstew/commit/bff357bd0cd2ce2e73113ae109ee0b713a849c89)

- Add: Vertical slice implementation plan for spec #30. [8f5c872](https://github.com/callowayproject/mindstew/commit/8f5c872a58076f13499d9263dfa5407c949d60da)

- Add: Documentation for triage labels and local settings adjustments. [70917af](https://github.com/callowayproject/mindstew/commit/70917af8ac35332374ccf95cc3022923c32c2a23)

- Add: Enable Claude plugin settings in configuration. [2dedbaf](https://github.com/callowayproject/mindstew/commit/2dedbaf9574c39113c4447ab26e8b01bd2a3443f)

### Other

- Bump the github-actions group with 2 updates. [c42a688](https://github.com/callowayproject/mindstew/commit/c42a688ef577ce890edd5d066a83b98ada7d58f5)

  Bumps the github-actions group with 2 updates: [actions/checkout](https://github.com/actions/checkout) and [actions/download-artifact](https://github.com/actions/download-artifact).

  Updates `actions/checkout` from 4 to 7

  - [Release notes](https://github.com/actions/checkout/releases)
  - [Changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md)
  - [Commits](https://github.com/actions/checkout/compare/v4...v7)

  Updates `actions/download-artifact` from 4 to 8

  - [Release notes](https://github.com/actions/download-artifact/releases)
  - [Commits](https://github.com/actions/download-artifact/compare/v4...v8)

  ______________________________________________________________________

  **updated-dependencies:** - dependency-name: actions/checkout
  dependency-version: '7'
  dependency-type: direct:production
  update-type: version-update:semver-major
  dependency-group: github-actions

  **signed-off-by:** dependabot[bot] <support@github.com>

- Bump the github-actions group with 10 updates. [b0b4de6](https://github.com/callowayproject/mindstew/commit/b0b4de6acb87f8f451d9e63c50937e3ff8d01c75)

  Bumps the github-actions group with 10 updates:

  | Package | From | To |
  | --- | --- | --- |
  | [actions/checkout](https://github.com/actions/checkout) | `4` | `7` |
  | [actions/setup-python](https://github.com/actions/setup-python) | `5` | `7` |
  | [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) | `5` | `7` |
  | [github/codeql-action](https://github.com/github/codeql-action) | `3` | `4` |
  | [docker/login-action](https://github.com/docker/login-action) | `3` | `4` |
  | [docker/metadata-action](https://github.com/docker/metadata-action) | `5` | `6` |
  | [docker/build-push-action](https://github.com/docker/build-push-action) | `6` | `7` |
  | [actions/attest-build-provenance](https://github.com/actions/attest-build-provenance) | `2` | `4` |
  | [actions/download-artifact](https://github.com/actions/download-artifact) | `4` | `8` |
  | [softprops/action-gh-release](https://github.com/softprops/action-gh-release) | `2` | `3` |

  Updates `actions/checkout` from 4 to 7

  - [Release notes](https://github.com/actions/checkout/releases)
  - [Changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md)
  - [Commits](https://github.com/actions/checkout/compare/v4...v7)

  Updates `actions/setup-python` from 5 to 7

  - [Release notes](https://github.com/actions/setup-python/releases)
  - [Commits](https://github.com/actions/setup-python/compare/v5...v7)

  Updates `astral-sh/setup-uv` from 5 to 7

  - [Release notes](https://github.com/astral-sh/setup-uv/releases)
  - [Commits](https://github.com/astral-sh/setup-uv/compare/v5...v7)

  Updates `github/codeql-action` from 3 to 4

  - [Release notes](https://github.com/github/codeql-action/releases)
  - [Changelog](https://github.com/github/codeql-action/blob/main/CHANGELOG.md)
  - [Commits](https://github.com/github/codeql-action/compare/v3...v4)

  Updates `docker/login-action` from 3 to 4

  - [Release notes](https://github.com/docker/login-action/releases)
  - [Commits](https://github.com/docker/login-action/compare/v3...v4)

  Updates `docker/metadata-action` from 5 to 6

  - [Release notes](https://github.com/docker/metadata-action/releases)
  - [Commits](https://github.com/docker/metadata-action/compare/v5...v6)

  Updates `docker/build-push-action` from 6 to 7

  - [Release notes](https://github.com/docker/build-push-action/releases)
  - [Commits](https://github.com/docker/build-push-action/compare/v6...v7)

  Updates `actions/attest-build-provenance` from 2 to 4

  - [Release notes](https://github.com/actions/attest-build-provenance/releases)
  - [Changelog](https://github.com/actions/attest-build-provenance/blob/main/RELEASE.md)
  - [Commits](https://github.com/actions/attest-build-provenance/compare/v2...v4)

  Updates `actions/download-artifact` from 4 to 8

  - [Release notes](https://github.com/actions/download-artifact/releases)
  - [Commits](https://github.com/actions/download-artifact/compare/v4...v8)

  Updates `softprops/action-gh-release` from 2 to 3

  - [Release notes](https://github.com/softprops/action-gh-release/releases)
  - [Changelog](https://github.com/softprops/action-gh-release/blob/master/CHANGELOG.md)
  - [Commits](https://github.com/softprops/action-gh-release/compare/v2...v3)

  ______________________________________________________________________

  **updated-dependencies:** - dependency-name: actions/checkout
  dependency-version: '7'
  dependency-type: direct:production
  update-type: version-update:semver-major
  dependency-group: github-actions

  **signed-off-by:** dependabot[bot] <support@github.com>

- Cleanup of files. [fec8750](https://github.com/callowayproject/mindstew/commit/fec875038510ea5a918425518626e17e1549636e)

### Updates

- Update: Improve CONTRIBUTING.md and CLAUDE.md guidelines for bug reports, enhancements, and PR processes. [34ba4ab](https://github.com/callowayproject/mindstew/commit/34ba4ab8c2c06ef1f9ba5a7a74f0673686966cab)

- Remove: Three-pane UI prototype (#7). [1169c11](https://github.com/callowayproject/mindstew/commit/1169c119a1af70be1f681a473290b3adec101926)

- Change: Make vault scaffold idempotent, drop derived READMEs (#31). [f0e96a9](https://github.com/callowayproject/mindstew/commit/f0e96a932e1564c1572419ebae79b0a8cf08252a)

## 0.1.0 (2026-10-04)

### New

- Add boilerplate. [59f0389](https://github.com/callowayproject/mindstew/commit/59f03898ca1cda00e6f1140df00f17cba00e7315)

- Add: Initial draft of Wayfinder design docs for core features. [3553202](https://github.com/callowayproject/mindstew/commit/35532020cf7781a7eb6911a69b8b21af5faa0e29)

- Add: Design doc for multimodal image captioning pipeline (issue #20). [737e5d8](https://github.com/callowayproject/mindstew/commit/737e5d84a8741e83d23d572f1f69054e23f1a44b)

- Add: Mockup for "Inbox" layout of grill-with-ui skill (HTML + template). [c7fc280](https://github.com/callowayproject/mindstew/commit/c7fc28016c1acbe75e207027648718a0bd49763d)

### Other

- Research: Mermaid rendering in QtWebEngine (issue #25). [0c16a72](https://github.com/callowayproject/mindstew/commit/0c16a729b3024b682bb1f7c25ee7fa6bdc967b4d)

- Research: filesystem confinement for shell_exec (issue #16). [e835cc0](https://github.com/callowayproject/mindstew/commit/e835cc01bfe16f071b8244d3a6be27b8a7e7b20f)

  Findings on sandbox-exec/Seatbelt profiles, chroot, and macOS container
  options for confining the chat agent's shell_exec tool to the vault root,
  sourced from man pages and live testing.

- Prototype: three-pane UI layout variants for wayfinder issue #7. [1ba37d5](https://github.com/callowayproject/mindstew/commit/1ba37d5a3c90c478fd1595ceb4d58aec465d6a56)

  Throwaway PySide6 prototype, not for main. Answers: panel proportions,
  resize/collapse behavior, activity panel placement, review queue surfacing.
  Variant B (command center) was selected.

- Research: macOS packaging/signing/notarization/update mechanism (issue #6). [b409eff](https://github.com/callowayproject/mindstew/commit/b409eff75aba8a9b9b1f9af295e3b76eca7e60fe)

  Findings on PyInstaller vs py2app for QtWebEngine bundling, hardened-runtime
  entitlements and inside-out signing for QtWebEngineProcess, and update
  mechanism options (Sparkle vs DIY GitHub Releases check) for direct
  distribution.

- Research: Python architecture for the tool-using chat agent (issue #4). [39a807e](https://github.com/callowayproject/mindstew/commit/39a807e099b6bcde866b11bfd65c228644d8a516)

- Research: LanceDB embedding & chunking strategy (issue #5). [06cb90d](https://github.com/callowayproject/mindstew/commit/06cb90de3e752e2fc693b24b2c780acf44b496fc)

- Initial commit: scaffold agent skills config. [b465ca9](https://github.com/callowayproject/mindstew/commit/b465ca9058670713c2c5408a361baca2cf97d89f)

  Sets up CLAUDE.md with GitHub issue tracker and domain docs pointers.
