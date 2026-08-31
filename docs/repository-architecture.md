# Repository Architecture

`wonderbell-skills` is a public control plane for a curated Codex Skill setup. It gives users one place to discover, classify, install, and audit Skills without republishing every upstream source.

## Source layers

### First-party Skills

Original, long-lived Skills maintained in this repository live under `skills/` and are declared in `catalog/custom.yaml`.

These files may be changed and released directly from this repository.

### External Skill suites

Skills maintained in other repositories remain with their original maintainers. `catalog/third-party.yaml` records their repository, branch, checkout, and Skill path. The installer checks out each source under the ignored `vendor/` directory and links enabled Skills into the user's Codex Skills directory.

Do not copy external Skill source into this repository merely to create a single folder. Keeping the upstream repository authoritative preserves attribution, licensing, updates, and independent release history.

### Codex-provided Skills

Codex system or runtime Skills are recorded in `catalog/builtins.yaml` for discovery and environment checks. They are not redistributed by this repository.

### Device-local experiments

Temporary or source-unknown Skills may remain local while their provenance and long-term ownership are unresolved. The audit tools report them as `unknown`; they should not be copied into the public repository until their source and license are known.

## Integration model

"Integrated" means:

- one public catalog and installation entry point;
- one visible source classification for every installed Skill;
- first-party Skills versioned here;
- external suites referenced rather than duplicated;
- generated machine state stored outside Git;
- source-specific installers or global runtime changes kept in their owning repositories.

It does not mean merging unrelated histories, licenses, release cycles, or global configuration into one monolithic repository.

## Repository ownership boundaries

- `wonderbell-skills` owns the public catalog, first-party Skills, local audit tooling, and top-level installation experience.
- Agentic workflow suites own their coordinated Skill set, compatibility migration, installer, and any managed global runtime guidance.
- External projects such as PM, Obsidian, and design Skill collections remain authoritative for their own source.

When an external suite changes its public names or installation contract, update this repository only after that suite publishes or provides a verified compatibility mapping.

The catalog may be prepared against a verified migration commit before its target repository URL is live, but it must not be published until that upstream URL and every enabled Skill path are reachable.

## Public-release rules

Before publishing a release or changing repository visibility:

1. scan the current tree and reachable Git history for credentials and private material;
2. keep machine-specific audit snapshots outside the repository;
3. verify first-party Skill ownership and third-party attribution;
4. include a repository license and preserve any nested third-party license notices;
5. run the installer and audit tests;
6. verify GitHub visibility, default branch, links, and installation commands after publication.
