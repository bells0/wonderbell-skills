# Install this Skill

This file is for the receiving agent. The business user should not copy files, locate a Skills directory, run installation commands, or configure runtime dependencies.

When the user asks to install this package:

1. If the user supplied a ZIP archive, extract it to a temporary working location yourself.
2. Inspect the current agent product's documented Skill or extension mechanism. Use its built-in import flow when available.
3. Install the entire `openai-compatible-imagegen` folder, preserving `SKILL.md`, `scripts/`, `references/`, and optional `agents/` metadata. Do not install only one script.
4. Prefer the current user's Skill scope instead of a machine-wide or administrator scope unless the user explicitly requests otherwise.
5. Verify that the installed `SKILL.md` is discoverable by the current agent. Report the resolved installation location.
6. On Windows, verify that `powershell.exe` is available. Do not require Python, Node.js, a package manager, or developer tools.
7. If Seedream is not configured, open `scripts\setup-seedream.cmd` in a user-visible window. The user only pastes the Key into the hidden local prompt. Never request, read, or echo the Key in chat.
8. After configuration, run `scripts\generate-image.ps1` with `-Check` and a harmless prompt. This validates local configuration without calling the provider or consuming quota.
9. Report `installed`, `configured`, and `local check passed` separately. Do not perform a paid generation until the user asks for an image and authorizes any reference-image upload.

If the current agent cannot import a Skill folder or execute local scripts, state that product limitation. Do not transfer the installation work to the non-technical user.
