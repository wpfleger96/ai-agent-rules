# CHANGELOG


## v0.26.0 (2026-03-06)

### Features

- Try out new codex model
  ([`d757b0b`](https://github.com/wpfleger96/ai-rules/commit/d757b0bda05f789e43f5483dacd036a0777779e5))


## v0.25.0 (2026-03-03)

### Features

- **pr-creator**: Add formatting rules for code identifiers, links, and line wrapping
  ([`8b36304`](https://github.com/wpfleger96/ai-rules/commit/8b36304a68e85701bc6aebc08608614ac37a844c))


## v0.24.0 (2026-02-27)

### Features

- Codex CLI support
  ([`6c6e01d`](https://github.com/wpfleger96/ai-rules/commit/6c6e01d1d063c1229ac1494254c69a61efa1a436))


## v0.23.2 (2026-02-27)

### Bug Fixes

- Fuck it
  ([`0168bbc`](https://github.com/wpfleger96/ai-rules/commit/0168bbc5ef745d5f0690c553a2d394e2cb3ccc46))


## v0.23.1 (2026-02-23)

### Bug Fixes

- Prefer local code exploration
  ([`0256efd`](https://github.com/wpfleger96/ai-rules/commit/0256efdcdbbbd6f3c5e0781392c6d9b4f0435ffb))


## v0.23.0 (2026-02-18)

### Features

- Gas up Sonnet
  ([`dfe0fbc`](https://github.com/wpfleger96/ai-rules/commit/dfe0fbc6c7ccf1b94415f55ab765937ae62b5a3b))


## v0.22.5 (2026-02-17)

### Bug Fixes

- Skill permissions
  ([`1d28665`](https://github.com/wpfleger96/ai-rules/commit/1d28665ff2ff94100e922cdea6ca9a721a59f915))

### Chores

- Update AGENTS.md and cleanup dead code
  ([`666139f`](https://github.com/wpfleger96/ai-rules/commit/666139fda2cc56b3956ca43a9abdfcb54ee86d36))

Removed empty performance/benchmark infrastructure (tests/performance/, .benchmarks/ data, 7
  Justfile recipes). Updated AGENTS.md to match current codebase: fixed project structure tree
  (removed nonexistent commands/hooks dirs, added all 9 skills), removed stale Quick Commands.
  Updated README.md to remove references to deleted Justfile targets.


## v0.22.4 (2026-02-14)

### Bug Fixes

- Unhelpful commit messages
  ([`abc1ff7`](https://github.com/wpfleger96/ai-rules/commit/abc1ff7542210629fb5081640676313e80f38dc2))

- Validate command bug
  ([`8eb0684`](https://github.com/wpfleger96/ai-rules/commit/8eb0684a9c7ab1ddc7a793743cc5d399c0e71c2f))


## v0.22.3 (2026-02-14)

### Bug Fixes

- Background update causing bugs
  ([`3f6b3ec`](https://github.com/wpfleger96/ai-rules/commit/3f6b3ecdfc5870e9e12bec86537001d1a3378d39))


## v0.22.2 (2026-02-12)

### Bug Fixes

- Improve dev-docs quality
  ([`6a8fc6f`](https://github.com/wpfleger96/ai-rules/commit/6a8fc6f3d6c79f0091a833686079a725c2f74023))


## v0.22.1 (2026-02-09)

### Bug Fixes

- Cc perm
  ([`66c0c8d`](https://github.com/wpfleger96/ai-rules/commit/66c0c8de39b9a4534845ff840febdaf8bc0b9afb))


## v0.22.0 (2026-02-09)

### Bug Fixes

- Clean up commit messages and PR descriptions
  ([`2e63bae`](https://github.com/wpfleger96/ai-rules/commit/2e63bae1691bdde4e1cf5ee1570ab7592f8281cb))

- Skill model configs
  ([`8485d41`](https://github.com/wpfleger96/ai-rules/commit/8485d41586a429dadf22dfa0bcbaba4de95ab823))

### Features

- Add content diffs to diff/install commands and fix cache staleness
  ([`1ddb125`](https://github.com/wpfleger96/ai-rules/commit/1ddb125cfc0b8f52ba88d16ea90a958493254572))

- Show unified diffs in diff/install/status commands when symlinks are mispointed or regular files
  exist instead of symlinks - Add content-based cache staleness check as fallback after mtime checks
  - Deduplicate cache comparison logic via get_cache_diff - Fix duplicate agent header and broken
  symlink handling edge cases


## v0.21.8 (2026-02-06)

### Bug Fixes

- Nerfed
  ([`4d8f17b`](https://github.com/wpfleger96/ai-rules/commit/4d8f17bd4b338ef04e62de41fbfbc9e80fed0757))


## v0.21.7 (2026-02-05)

### Bug Fixes

- Cc perm
  ([`bdb454a`](https://github.com/wpfleger96/ai-rules/commit/bdb454ae98b2d451bc3002e5b3c356398d46d6bf))


## v0.21.6 (2026-02-05)

### Bug Fixes

- Gas up work profile
  ([`ad93453`](https://github.com/wpfleger96/ai-rules/commit/ad93453a80127ae9baf7a3c50940a661c14209d7))


## v0.21.5 (2026-02-05)

### Bug Fixes

- Opus 4.6 just dropped
  ([`d3868ca`](https://github.com/wpfleger96/ai-rules/commit/d3868caa9db4e6e3dc60cb5452f8f00e519a6e3a))


## v0.21.4 (2026-02-04)

### Bug Fixes

- Cc perms
  ([`9a69359`](https://github.com/wpfleger96/ai-rules/commit/9a693591b7ff56f50d3ca261c5258b14e3533a19))

- Improve top-level AGENTS.md instructions
  ([`e548a5b`](https://github.com/wpfleger96/ai-rules/commit/e548a5b378f965523fb45067069a07f62e2a496b))


## v0.21.3 (2026-02-04)

### Bug Fixes

- Cc perm
  ([`4881d81`](https://github.com/wpfleger96/ai-rules/commit/4881d810dad44f646b6df100e3f7cf37f94e7954))


## v0.21.2 (2026-02-03)

### Bug Fixes

- Cc perm
  ([`fbf64ad`](https://github.com/wpfleger96/ai-rules/commit/fbf64adf814df8406637f4e940504a3ca3b159b6))


## v0.21.1 (2026-01-28)

### Bug Fixes

- Migrate code-reviewer to skill too
  ([`6b35f74`](https://github.com/wpfleger96/ai-rules/commit/6b35f74efaf5793af970e57188531eca9a2a5039))

migrate to skill to align with the rest of the repo, aupport both local and PR review , and enhance
  prompts using content from Google eng best practices blog: 1.
  https://google.github.io/eng-practices/review/reviewer/standard.html 2.
  https://google.github.io/eng-practices/review/reviewer/looking-for.html


## v0.21.0 (2026-01-28)

### Documentation

- Add full automated CLI reference docs
  ([`8f355a0`](https://github.com/wpfleger96/ai-rules/commit/8f355a08e72fc8c626aad48d45910de32e276fc3))

### Features

- Convert and consolidate CC slash commands into skills
  ([`2a99382`](https://github.com/wpfleger96/ai-rules/commit/2a99382e8338954ab2837a1920a14b8a46c23126))

### Refactoring

- Convert and consolidate CC slash commands into skills to align with Anthropic change
  ([`9995fa5`](https://github.com/wpfleger96/ai-rules/commit/9995fa5ff5cecf304a5ba866730a051788e2419f))


## v0.20.10 (2026-01-23)

### Bug Fixes

- Cc perm
  ([`de4759d`](https://github.com/wpfleger96/ai-rules/commit/de4759d517e358a859f1ec2f52ff49bdb8c46160))


## v0.20.9 (2026-01-23)

### Bug Fixes

- Unnecessary output
  ([`765f530`](https://github.com/wpfleger96/ai-rules/commit/765f5307f6ed407253a503eca8d3e827337bb72a))


## v0.20.8 (2026-01-23)

### Bug Fixes

- Standardize wording
  ([`4def6ae`](https://github.com/wpfleger96/ai-rules/commit/4def6ae022165cad20d7b8cd1b73aca7c04e2a53))


## v0.20.7 (2026-01-23)

### Bug Fixes

- Goose config
  ([`9c1717f`](https://github.com/wpfleger96/ai-rules/commit/9c1717fade8d6de2d3537b7c194b429e70be7feb))


## v0.20.6 (2026-01-22)

### Bug Fixes

- Cleanup orphaned hooks
  ([`8ebee1b`](https://github.com/wpfleger96/ai-rules/commit/8ebee1bda9aafffa791c584f980e804399886313))

- Cleanup vestigial post-merge hook code
  ([`064a766`](https://github.com/wpfleger96/ai-rules/commit/064a7661377a5ff3facbdafb2025ee71b757f2a9))


## v0.20.5 (2026-01-22)

### Bug Fixes

- Show unified diffs for all config drift detection types
  ([`98952cf`](https://github.com/wpfleger96/ai-rules/commit/98952cfeb4e75c38ee8af295a283d353b9697490))


## v0.20.4 (2026-01-22)

### Bug Fixes

- Cc perm
  ([`016e409`](https://github.com/wpfleger96/ai-rules/commit/016e4097de5194f9b09220d04213e0e3a5c00662))


## v0.20.3 (2026-01-22)

### Bug Fixes

- Forgot to cleanup a few
  ([`7eca265`](https://github.com/wpfleger96/ai-rules/commit/7eca265e3854e8a7c60cff8a53b663466d5501d5))


## v0.20.2 (2026-01-22)

### Bug Fixes

- Standardize --yes vs --force flags
  ([`a6f55d8`](https://github.com/wpfleger96/ai-rules/commit/a6f55d8a2338838ddf903f305eb3e18bc7b630af))

### Chores

- Docs
  ([`8b10c99`](https://github.com/wpfleger96/ai-rules/commit/8b10c99c3baa0f65e73b8384fbb71c616d66e3e1))


## v0.20.1 (2026-01-21)

### Bug Fixes

- Claude code and goose agents should share skills since it's a common standard
  ([`e492a54`](https://github.com/wpfleger96/ai-rules/commit/e492a54975411f3b0c2155c6be573124e8cbe0a5))

this was the intention in ae91931 but didn't fully get finished

- Don't overwrite hooks manually setup by the user
  ([`072b22c`](https://github.com/wpfleger96/ai-rules/commit/072b22c050e422a305eb828733663b96ee649bf0))

or any other configs either, intelligently merge and note local overrides as unmanaged

- Standardize output
  ([`b16d53e`](https://github.com/wpfleger96/ai-rules/commit/b16d53ee7b1a44ed2e74c0b987c9b6b687022484))


## v0.20.0 (2026-01-21)

### Bug Fixes

- Cc perm
  ([`9747329`](https://github.com/wpfleger96/ai-rules/commit/97473292a4465c0b21fe37d8d47b2eec903c6eeb))

### Features

- Add full skills support for claude code and goose
  ([`ae91931`](https://github.com/wpfleger96/ai-rules/commit/ae91931e18606f7849fefc64d07937999680bb24))

also disabling skill router hook temporarily


## v0.19.9 (2026-01-21)

### Bug Fixes

- Cc perm
  ([`514a67c`](https://github.com/wpfleger96/ai-rules/commit/514a67caa05bcee3ef4eca802142415e4a35e0d5))


## v0.19.8 (2026-01-21)

### Bug Fixes

- Improved skills and added test-writer skill
  ([`d2720f9`](https://github.com/wpfleger96/ai-rules/commit/d2720f9e0f9915c13a5b48d5e1f8a7f8805ef2ea))

- Tweak agents-md slash command prompts
  ([`c9414c1`](https://github.com/wpfleger96/ai-rules/commit/c9414c1134b991935ce622ba306eb8885fa14a4c))


## v0.19.7 (2026-01-20)

### Bug Fixes

- Auto force install during upgrade, don't double prompt user
  ([`eea1d26`](https://github.com/wpfleger96/ai-rules/commit/eea1d2681bcb6f03e28cc6c6f868dd1b42003399))

- Don't run pending update check when already running upgrade command
  ([`e368c9c`](https://github.com/wpfleger96/ai-rules/commit/e368c9cd0737a05d72f920f5f3be50d688b19086))

otherwise this would cause confusing double-prompting

- Show changelog(s) when upgrading
  ([`2b69973`](https://github.com/wpfleger96/ai-rules/commit/2b6997365ae167ee9cd2cbf3b5071a2eefaf066e))

### Chores

- Docs
  ([`6f496f4`](https://github.com/wpfleger96/ai-rules/commit/6f496f49864f8b8de36c0e259d6e30b4bd626a9a))


## v0.19.6 (2026-01-19)

### Bug Fixes

- Cc perm
  ([`3fbef62`](https://github.com/wpfleger96/ai-rules/commit/3fbef62dcbbc7af2cb376a794407895e6a3dce2a))

- Cleanup orphaned plugins that we uninstalled
  ([`104b480`](https://github.com/wpfleger96/ai-rules/commit/104b48036d4d5b377ae003aa45295cd9edd85beb))

- Llms love dumb comments
  ([`32e059d`](https://github.com/wpfleger96/ai-rules/commit/32e059d3e9bd85cff204a560e64ba91f3bd24723))


## v0.19.5 (2026-01-18)

### Bug Fixes

- Cleanup unused tools
  ([`06a1880`](https://github.com/wpfleger96/ai-rules/commit/06a1880bffa819b5814784b286f1609505ed943f))

- Show unified diffs instead of just file path diffs
  ([`2202516`](https://github.com/wpfleger96/ai-rules/commit/2202516e92d4d5af95416c9d82033817cef3f1ee))


## v0.19.4 (2026-01-18)

### Bug Fixes

- Lazyify imports for completion performance
  ([`4df5109`](https://github.com/wpfleger96/ai-rules/commit/4df5109516e7668b619fc6b22627b767704ad89a))


## v0.19.3 (2026-01-18)

### Bug Fixes

- Cc perm
  ([`6441d43`](https://github.com/wpfleger96/ai-rules/commit/6441d439828379a35df928a2dcad3c493d17a3a3))


## v0.19.2 (2026-01-13)

### Bug Fixes

- Dont prompt for reinstall when unmanaged plugins/skills detected
  ([`146da20`](https://github.com/wpfleger96/ai-rules/commit/146da206c92c19f33a85b66fad9e46b485ae4d33))


## v0.19.1 (2026-01-12)

### Bug Fixes

- Cc perm
  ([`21513a6`](https://github.com/wpfleger96/ai-rules/commit/21513a6c40224278bd7a2a3f2033681a5be43a77))


## v0.19.0 (2026-01-09)

### Features

- /prompt-critique slash command
  ([`7c9435d`](https://github.com/wpfleger96/ai-rules/commit/7c9435dfe12888efbdacdf650138f9748225349c))

- /refresh-plan slash command
  ([`64da261`](https://github.com/wpfleger96/ai-rules/commit/64da261fe1b842ae891ff97c87b968e5af7e4f87))


## v0.18.5 (2026-01-09)

### Bug Fixes

- Cc perm
  ([`bbf729b`](https://github.com/wpfleger96/ai-rules/commit/bbf729bf48b379cbc03dde7f1b512e451df2d4d8))


## v0.18.4 (2026-01-09)

### Bug Fixes

- Cc perm
  ([`9ea6eff`](https://github.com/wpfleger96/ai-rules/commit/9ea6eff12e45b6abbabb5e88d70b67a77e679bbf))

### Chores

- Docs
  ([`0d6b540`](https://github.com/wpfleger96/ai-rules/commit/0d6b540817c8b8303f5a1ac71df12f72014630e5))


## v0.18.3 (2026-01-09)

### Bug Fixes

- Auto enable plugins
  ([`f4dafb7`](https://github.com/wpfleger96/ai-rules/commit/f4dafb74cd02464ef96bbeb669d6c790514668b8))


## v0.18.2 (2026-01-09)

### Bug Fixes

- Plugin
  ([`c695c3d`](https://github.com/wpfleger96/ai-rules/commit/c695c3dc0d4334284a2403077de2aee11bae3e93))


## v0.18.1 (2026-01-08)

### Bug Fixes

- Wordy PR descriptions
  ([`1a9fc3a`](https://github.com/wpfleger96/ai-rules/commit/1a9fc3a66bc4a72aaa5b17a2620a15ab69394d1a))


## v0.18.0 (2026-01-08)

### Chores

- Clean up vestigial code
  ([`b86a53f`](https://github.com/wpfleger96/ai-rules/commit/b86a53fa15685224d94491c1f1ccb3cc05fd09c8))

- Docs
  ([`41ff2bb`](https://github.com/wpfleger96/ai-rules/commit/41ff2bba0e5256160fe4e08fbc48e00d39afb8f0))

### Features

- Add claude code plugin support
  ([`2e18fa4`](https://github.com/wpfleger96/ai-rules/commit/2e18fa408f3fabcbcee5f664639017e383c3ac47))


## v0.17.0 (2025-12-20)

### Features

- Migrating cursor settings to shell-configs project
  ([`b95ea16`](https://github.com/wpfleger96/ai-rules/commit/b95ea16e327eba3c4ed2a543d98f7f239f2b3cbb))


## v0.16.1 (2025-12-20)

### Bug Fixes

- Optimize token usage
  ([`bb93497`](https://github.com/wpfleger96/ai-rules/commit/bb93497f41fc32fcad2064fbec0cb97f2aa8fbfb))

### Chores

- Docs
  ([`78ee562`](https://github.com/wpfleger96/ai-rules/commit/78ee56246d8639ed7492b3605126ae6c573f85e8))


## v0.16.0 (2025-12-19)

### Bug Fixes

- /update-docs should auto invoke doc-writer skill, and remove unnecessary update command
  ([`93c8f72`](https://github.com/wpfleger96/ai-rules/commit/93c8f72589f17e08363a76e74ec4f0222493435b))

### Features

- Userpromptsubmit hook to force skill activation, and claude code only autoloads skill frontmatter
  so put activation instructions there
  ([`fa37479`](https://github.com/wpfleger96/ai-rules/commit/fa374794e912dc8e87f5f063e8ffbe61fe413409))


## v0.15.15 (2025-12-18)

### Bug Fixes

- Clarify between user/manual vs. profile overrides
  ([`975694e`](https://github.com/wpfleger96/ai-rules/commit/975694e54e734e6dd68477921f91ff42dbcd2537))


## v0.15.14 (2025-12-18)

### Bug Fixes

- All commands should respect current profile if set
  ([`2a7cdd9`](https://github.com/wpfleger96/ai-rules/commit/2a7cdd90f2ba8fe9c8dda127bd8109caa44d36a6))


## v0.15.13 (2025-12-18)

### Bug Fixes

- Add completions status command
  ([`5fbe247`](https://github.com/wpfleger96/ai-rules/commit/5fbe2472ebd08262767ab9c4fb0162e58a6ef939))


## v0.15.12 (2025-12-18)

### Bug Fixes

- Get prompt-engineer skill to auto trigger
  ([`5490942`](https://github.com/wpfleger96/ai-rules/commit/5490942778813fa8aa59980c628877dda62f0a00))

### Chores

- Cleanup dead code
  ([`b98d4d7`](https://github.com/wpfleger96/ai-rules/commit/b98d4d7f5fad5eb40eb1ebde6ef8518ea8305c58))


## v0.15.11 (2025-12-18)

### Bug Fixes

- Switching profiles should gracefully handle conflicting overrides
  ([`7080a3d`](https://github.com/wpfleger96/ai-rules/commit/7080a3df51608381be23805080765622828a6125))


## v0.15.10 (2025-12-17)

### Bug Fixes

- Remove useless hook
  ([`ad4d540`](https://github.com/wpfleger96/ai-rules/commit/ad4d5403a12ca7f8a5f64041da1c43c513117038))


## v0.15.9 (2025-12-17)

### Bug Fixes

- Intelligent uninstall+reinstall logic
  ([`09274c4`](https://github.com/wpfleger96/ai-rules/commit/09274c43a3856850e6f33908e971cc39a3737101))


## v0.15.8 (2025-12-17)

### Bug Fixes

- Remove local install option expose info command for troubleshooting
  ([`b998e5d`](https://github.com/wpfleger96/ai-rules/commit/b998e5d0d2e638e117f6b06f1950c963f9c7e68f))


## v0.15.7 (2025-12-17)

### Bug Fixes

- Dryrun/force flags and cc perms
  ([`5f0d73e`](https://github.com/wpfleger96/ai-rules/commit/5f0d73e3b680ab5624f00bc19a41890ca7b9894c))

- Setup commmand should also upgrade if already installed
  ([`f381cef`](https://github.com/wpfleger96/ai-rules/commit/f381cef83c2bfeb6aed9006660d44da10b574139))


## v0.15.6 (2025-12-17)

### Bug Fixes

- **upgrade**: Flaky upgrade for GitHub-based installs
  ([`a8ed872`](https://github.com/wpfleger96/ai-rules/commit/a8ed872c20b0a0cae6cd2c17de6b7c45d0b720ac))


## v0.15.5 (2025-12-11)

### Bug Fixes

- Update code comment instructions
  ([`ef78069`](https://github.com/wpfleger96/ai-rules/commit/ef78069ac6f4b2838251737a681deb74acc4019f))

### Chores

- Docs
  ([`9a2dbdc`](https://github.com/wpfleger96/ai-rules/commit/9a2dbdc01e36a8eab3303bb75cc1a3371ca743a1))


## v0.15.4 (2025-12-11)

### Bug Fixes

- Profile should show current and let you switch
  ([`7133c0e`](https://github.com/wpfleger96/ai-rules/commit/7133c0e4e480f4f23c4b0b5ab1de64dceaf13c77))


## v0.15.3 (2025-12-11)

### Bug Fixes

- This burns through pro sub
  ([`828de97`](https://github.com/wpfleger96/ai-rules/commit/828de97921774e45a416fc953c6cb30ced90eda6))

### Chores

- Docs
  ([`859d3b4`](https://github.com/wpfleger96/ai-rules/commit/859d3b4c3c448e591b0fd4a80065616ecc5dfc7a))


## v0.15.2 (2025-12-11)

### Bug Fixes

- Goosehints not getting built in wheel
  ([`c0c4b8b`](https://github.com/wpfleger96/ai-rules/commit/c0c4b8be353b0f66cf38655398e42eeba847435b))


## v0.15.1 (2025-12-11)

### Bug Fixes

- Statusline install should respect install source
  ([`8b0bada`](https://github.com/wpfleger96/ai-rules/commit/8b0bada7a725ddc74ac4aa25b5e4fd45164bc9b2))


## v0.15.0 (2025-12-10)

### Features

- Add github installation support
  ([`a7c00cf`](https://github.com/wpfleger96/ai-rules/commit/a7c00cfb224b78ea089f2ada1ae394bdac514ba1))


## v0.14.0 (2025-12-10)

### Chores

- Update AGENTS.md
  ([`1f3e7fd`](https://github.com/wpfleger96/ai-rules/commit/1f3e7fd7dc33b928f6ff3e03397abb7cf6152e0a))

### Features

- Add profiles feature
  ([`f82159c`](https://github.com/wpfleger96/ai-rules/commit/f82159cb6752fc119a0820c009da8720fbe1879c))


## v0.13.0 (2025-12-10)

### Bug Fixes

- Dont install completions if already installed
  ([`b95e30d`](https://github.com/wpfleger96/ai-rules/commit/b95e30d8a170007d7070e4af2987b6dfaf2b87d2))

- Dont waste tokens, other hints files should @mention the main AGENTS.md
  ([`fab89e7`](https://github.com/wpfleger96/ai-rules/commit/fab89e721a851472d37f0af4cb7519c3c2501b0b))

### Features

- Add supported CursorAgent
  ([`b648e66`](https://github.com/wpfleger96/ai-rules/commit/b648e660730906ca6c3f017fc9ec8dabe05d0d0c))


## v0.12.4 (2025-12-09)

### Bug Fixes

- Cc perm
  ([`f895aa0`](https://github.com/wpfleger96/ai-rules/commit/f895aa0fc6aeb8f9921b9ddcb98dc38b28eede60))


## v0.12.3 (2025-12-08)

### Bug Fixes

- Uvx pip still uses pip config not uv
  ([`1593f0d`](https://github.com/wpfleger96/ai-rules/commit/1593f0d38f1781473a89ddec46d84fefe5ecff4e))


## v0.12.2 (2025-12-08)

### Bug Fixes

- Cc perm
  ([`7ffeb1a`](https://github.com/wpfleger96/ai-rules/commit/7ffeb1a17948a245bc1e2969cfe1307c78f0fc02))

### Chores

- Update AGENTS.md
  ([`86956f0`](https://github.com/wpfleger96/ai-rules/commit/86956f0121d8d2ba9e6d6cfb55e8bee1740c3fd0))


## v0.12.1 (2025-12-08)

### Bug Fixes

- Respect global package index settings
  ([`beb0fd4`](https://github.com/wpfleger96/ai-rules/commit/beb0fd4814007ca8d4df10c327c7a6c2059038a8))


## v0.12.0 (2025-12-08)

### Features

- Agents-md slash command
  ([`9edb6e3`](https://github.com/wpfleger96/ai-rules/commit/9edb6e30feeba26605d0b49921a3018964de397b))


## v0.11.0 (2025-12-08)

### Features

- Doc-writer skill and annotate-changelog slash command
  ([`0faaf4e`](https://github.com/wpfleger96/ai-rules/commit/0faaf4ece829a80fb646b5815b77398e48a45c86))


## v0.10.3 (2025-12-07)

### Bug Fixes

- Cc perms
  ([`9dd366c`](https://github.com/wpfleger96/ai-rules/commit/9dd366cd171480976fd25cc840256bf224453fe3))


## v0.10.2 (2025-12-07)

### Bug Fixes

- Still flaky
  ([`3a6a1ce`](https://github.com/wpfleger96/ai-rules/commit/3a6a1ce4b4b70e49cf0968b42ca78c90c2109ef5))


## v0.10.1 (2025-12-07)

### Bug Fixes

- Flaky update behavior
  ([`f894249`](https://github.com/wpfleger96/ai-rules/commit/f894249cf324fd6dfa86a6d99d6562386f1f9d85))

### Chores

- Update script
  ([`8ae0008`](https://github.com/wpfleger96/ai-rules/commit/8ae00088ee8e4db9f07c7f4f101c214f425c79e1))


## v0.10.0 (2025-12-06)

### Chores

- More code quality
  ([`f639929`](https://github.com/wpfleger96/ai-rules/commit/f639929156d919ea582140e151ee6114002d485a))

### Features

- Opus avaliable on pro now
  ([`c7e9969`](https://github.com/wpfleger96/ai-rules/commit/c7e9969fadc997bfa7fe70d463fcd0deafd92197))


## v0.9.5 (2025-12-05)

### Chores

- Code quality
  ([`9793b0e`](https://github.com/wpfleger96/ai-rules/commit/9793b0e22ab752bdf4deddfe9e2f083aff63d13a))


## v0.9.4 (2025-12-05)

### Bug Fixes

- Show diff during install
  ([`ea63ecc`](https://github.com/wpfleger96/ai-rules/commit/ea63ecc5996a2994325c3cdc6cc741441c4421ec))


## v0.9.3 (2025-12-05)

### Bug Fixes

- Cc perm
  ([`490ad02`](https://github.com/wpfleger96/ai-rules/commit/490ad0204b37f1553852f6dd96aceaf8556ce8c8))

- Llms are dumb
  ([`fd29f5b`](https://github.com/wpfleger96/ai-rules/commit/fd29f5b9e9c62064737853e29da7cb3e4fe63d74))


## v0.9.2 (2025-12-04)

### Bug Fixes

- Update daily and force --version to bypass cache
  ([`f2efa65`](https://github.com/wpfleger96/ai-rules/commit/f2efa653bfea854476c33e947078c1ade9d6e07d))

### Chores

- Add editor config and fix precommit bug
  ([`35693f0`](https://github.com/wpfleger96/ai-rules/commit/35693f0f986bc272ff90875ddf9424ab1c9d820e))


## v0.9.1 (2025-12-04)

### Bug Fixes

- Shell lint cmds
  ([`447463e`](https://github.com/wpfleger96/ai-rules/commit/447463e4da6b35c840e3201ec3c8a3d968e865b3))


## v0.9.0 (2025-12-04)

### Features

- Use shell registry for supported shells
  ([`623e375`](https://github.com/wpfleger96/ai-rules/commit/623e37544b15dd333baca55dc665d13d53fa8325))


## v0.8.1 (2025-12-04)

### Bug Fixes

- Install should install completions
  ([`6cbb669`](https://github.com/wpfleger96/ai-rules/commit/6cbb669a17121a7f9f1de076a9d11e4e254f3d2d))

### Chores

- Migrate repo to use Just
  ([`b139720`](https://github.com/wpfleger96/ai-rules/commit/b139720729344e12ea1877fdfac4e5b74f5305fa))

### Continuous Integration

- Prevent race condition in release workflow
  ([`9ee9827`](https://github.com/wpfleger96/ai-rules/commit/9ee982700ff78230726e715ae896c8c54e11d4e6))


## v0.8.0 (2025-12-04)

### Bug Fixes

- Detect and handle local wheel installations in upgrade command
  ([`41a9797`](https://github.com/wpfleger96/ai-rules/commit/41a97973cd7385c2124e1bffc309e8ec288380ea))

### Features

- Add shell completions support with auto install
  ([`f8c3bd8`](https://github.com/wpfleger96/ai-rules/commit/f8c3bd84a479d89aa4e83accf8d5bb64f856ef61))


## v0.7.0 (2025-12-03)

### Features

- Auto update statusline script
  ([`fbb4688`](https://github.com/wpfleger96/ai-rules/commit/fbb468850ac943ba37e6a1f162e4278632933f8e))


## v0.6.0 (2025-12-03)

### Documentation

- Update README
  ([`a8b1815`](https://github.com/wpfleger96/ai-rules/commit/a8b18150468d16ddd6a22384125d443192db4655))

### Features

- Auto install status line script
  ([`e09d21c`](https://github.com/wpfleger96/ai-rules/commit/e09d21c3740fdcc5a923431444b79c106db2d76c))


## v0.5.4 (2025-12-02)

### Bug Fixes

- Stop caching wrong symlink path when overrides exist
  ([`8611713`](https://github.com/wpfleger96/ai-rules/commit/86117135c0854acc7b370bc3c1d4325595003845))


## v0.5.3 (2025-12-02)

### Bug Fixes

- Performance improvements during symlink install
  ([`4cc1700`](https://github.com/wpfleger96/ai-rules/commit/4cc170055db596cf067a69d4b56d14f829e6f562))


## v0.5.2 (2025-12-02)

### Bug Fixes

- Symlink to tool install dir instead of uvx cache
  ([`9b9a617`](https://github.com/wpfleger96/ai-rules/commit/9b9a61730912c7378178d6db7c5b338a4481f149))

### Continuous Integration

- Fix publish workflow not running
  ([`3e184d6`](https://github.com/wpfleger96/ai-rules/commit/3e184d6c6fde4a1983a3929d2106ef3d0a1107ef))


## v0.5.1 (2025-12-02)

### Bug Fixes

- Test failures in CI and cleanup
  ([`02211d3`](https://github.com/wpfleger96/ai-rules/commit/02211d3c20c52825af0f9aacf2b90e22aa7fed04))

### Chores

- Add AGENTS.md for project
  ([`b871ea8`](https://github.com/wpfleger96/ai-rules/commit/b871ea8f52177c2c92adadeec50c39d364826b66))


## v0.5.0 (2025-12-02)

### Bug Fixes

- Make sure config files get built into wheel package
  ([`3c92f88`](https://github.com/wpfleger96/ai-rules/commit/3c92f88744705168af7a34ee650cd9be519da430))

### Continuous Integration

- Enable ad-hoc runs of publish workflow
  ([`4388662`](https://github.com/wpfleger96/ai-rules/commit/43886624aca953c8bf6f17bbbc368f08269382f9))

- Fix publish workflow bug
  ([`f09ab45`](https://github.com/wpfleger96/ai-rules/commit/f09ab455e7e6f89dc3db2a83028611aedf17482b))

### Features

- Show full diff for stale cache
  ([`cffabd8`](https://github.com/wpfleger96/ai-rules/commit/cffabd827e9adedc875c1f73a2796fc8aa132ae5))


## v0.4.1 (2025-12-02)

### Bug Fixes

- Expose both package names
  ([`dc78525`](https://github.com/wpfleger96/ai-rules/commit/dc78525b2ad019cdeaf4b713fa7ec054bc4ec77d))

### Chores

- Only run publish workflow if we released a new version tag
  ([`5b8488b`](https://github.com/wpfleger96/ai-rules/commit/5b8488b0d37aa38236bcfae466d96c88a1b41dd4))

- Readme badges
  ([`274b949`](https://github.com/wpfleger96/ai-rules/commit/274b949ce9d91a39bc23b861a6aa879be0c2bb3e))


## v0.4.0 (2025-12-02)

### Chores

- Ai spaghetti refactor
  ([`e1c0694`](https://github.com/wpfleger96/ai-rules/commit/e1c0694822c34320c2ad7ee0b9dee4667460eff8))

- Cleanup and another CI test fix
  ([`7acadcf`](https://github.com/wpfleger96/ai-rules/commit/7acadcf9b757f211d1fd306cace79e3932f6f131))

### Features

- Add bootstrap install and auto update processes
  ([`6569767`](https://github.com/wpfleger96/ai-rules/commit/65697676c24c08a2b5da7a0fb6deb6df0b065920))

- Publish to pypi
  ([`14e41f3`](https://github.com/wpfleger96/ai-rules/commit/14e41f3863284d08ddd645c9324ea741fed858d0))


## v0.3.0 (2025-12-01)

### Bug Fixes

- Address critical code review issues
  ([`8b97673`](https://github.com/wpfleger96/ai-rules/commit/8b976730ce1ca41c9e7c3cf5a69594baf457bd6f))

This commit fixes the critical and high-priority issues identified in the code review:

Critical Fixes: - Fix deep merge shallow copy bug - Use copy.deepcopy() instead of base.copy() to
  prevent mutation of base dictionaries (CRITICAL) - Add nested key support to override unset
  command - Now matches override set functionality for consistency

High-Priority Fixes: - Add cache invalidation/staleness detection - Cache is now checked against
  base settings and user config modification times - Optimize cache rebuilding - Cache only built
  during install, not on every get_symlinks() call (status checks are now read-only)

Technical Changes: - Added is_cache_stale() method to check if cache needs rebuilding - Added
  get_settings_file_for_symlink() for read-only symlink enumeration - Modified
  build_merged_settings() to skip rebuild when cache is fresh - Added force_rebuild parameter to
  build_merged_settings() - Cache building moved to install command, before symlink creation - Added
  7 new tests for cache invalidation logic

Test Results: - All 30 tests passing (23 original + 7 new) - Tests cover cache staleness detection,
  force rebuild, and file selection

Performance Impact: - Status/diff commands no longer rebuild cache unnecessarily - Cache
  automatically invalidates when base settings or overrides change - --rebuild-cache flag forces
  cache rebuild when needed

### Chores

- Couple more CC perms
  ([`2af58b4`](https://github.com/wpfleger96/ai-rules/commit/2af58b475f76e0900fce0a35d4911381ace03af9))

- Tweak AGENTS file
  ([`8b02b94`](https://github.com/wpfleger96/ai-rules/commit/8b02b94197dc50cd86cc8b69586bd1f45133a57f))

### Features

- Improve exclusion config UX and add settings merge functionality
  ([`673057a`](https://github.com/wpfleger96/ai-rules/commit/673057a8c5278ed913d698deaf11482f4a447737))

This commit significantly improves the user experience for managing exclusions and adds powerful
  settings override capabilities for machine-specific configurations.

Major Features: - Glob pattern support for exclusions (e.g., ~/.claude/*.json) - Settings overrides
  for machine-specific settings with deep merge - Interactive config wizard (ai-rules config init) -
  New CLI command groups: exclude, override, config - Settings cache management with --rebuild-cache
  flag

CLI Improvements: - ai-rules config init: Interactive wizard for first-time setup - ai-rules config
  show: View raw or merged settings - ai-rules config edit: Edit config in $EDITOR - ai-rules
  exclude add/remove/list: Manage exclusions - ai-rules override set/unset/list: Manage settings
  overrides

Settings Merge System: - Sync base settings.json via git - Override specific keys per machine (e.g.,
  model access) - Deep merge with caching in ~/.ai-rules/cache/ - Supports different settings across
  work/personal laptops

Technical Changes: - Added fnmatch for glob pattern matching in config.py - Implemented deep merge
  algorithm for settings - Added build_merged_settings() for cache management - Enhanced ClaudeAgent
  to use merged settings - Added 16 new tests covering glob patterns and merging

Documentation: - Comprehensive README updates with examples - Updated .ai-rules-config.yaml.example
  with detailed comments - Added troubleshooting section - Documented config precedence and merging
  behavior - Updated CHANGELOG.md

All tests passing (23 tests).

Fixes #[issue-number]


## v0.2.0 (2025-12-01)

### Bug Fixes

- Don't double-prompt the user for confirmation
  ([`54fa5e1`](https://github.com/wpfleger96/ai-rules/commit/54fa5e1399f78188854a3a8703382a5761343fc5))

### Chores

- Update README and readd MIT license
  ([`9bd4e65`](https://github.com/wpfleger96/ai-rules/commit/9bd4e65c4e790e15c5457d33f00db4a2e342ad57))

### Features

- Add SubagentStop hook, project-level rule support, shared AGENTS.md config, and post-merge hook
  ([`263e07c`](https://github.com/wpfleger96/ai-rules/commit/263e07cbf712afad6720c17fe4327818d80fedb1))

- Initial release
  ([`8a9c739`](https://github.com/wpfleger96/ai-rules/commit/8a9c73994c4b84f2754076d555bed68303d715fe))
