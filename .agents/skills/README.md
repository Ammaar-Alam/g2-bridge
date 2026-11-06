# Reverse-engineering skill snapshot

The owner explicitly requested `reverse-engineer-anything`. This folder includes the supplied skill, version 42, and all six local reference guides, copied on November 6, 2026. It is a portable instruction snapshot for this private investigation.

Start with [SKILL.md](reverse-engineer-anything/SKILL.md). The upstream project is [REA](https://github.com/morluto/rea). Use a matching installed skill when available and record its version. The snapshot does not install or configure the REA MCP server, Ghidra, JADX, Java, or any other engine.

The initial session's connected REA server reported version 6.7.0. Verify the Windows host independently. The [Android guide](reverse-engineer-anything/references/android-applications.md), [native guide](reverse-engineer-anything/references/native-and-artifacts.md), and [recovery guide](reverse-engineer-anything/references/connection-and-recovery.md) are the relevant starting references. Other guides are preserved so the skill's relative links remain usable.

`SHA256SUMS` records the copied files' bytes. These hashes identify the local snapshot; they are not an upstream signature or a verification of third-party binaries. Do not publish this private tool snapshot as part of the bridge's public code without reviewing whether it belongs in that release.
