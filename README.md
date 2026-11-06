# DJI Goggles 2 simulator bridge

Research toward displaying existing Windows FPV simulators, including Uncrashed, in **DJI Goggles 2**.

This repository has research and an investigation plan. **It does not yet contain a working video bridge.** No hardware video-input test has been performed.

The preferred outcome is a Windows application that sends the simulator's picture to stock goggles over USB. A small Raspberry Pi bridge is an acceptable fallback. The simulator continues to run on Windows.

## Continue the investigation

Clone the private repository on the Windows PC that runs the simulator:

```powershell
git clone https://github.com/Ammaar-Alam/dji-goggles2-sim-bridge.git
cd dji-goggles2-sim-bridge
```

Open this folder in Codex and start with [AGENTS.md](AGENTS.md), then [.agents/README.md](.agents/README.md). The [Windows handoff](.agents/WINDOWS.md) contains the next steps. A copy of the requested reverse-engineering skill is included under [.agents/skills](.agents/skills/README.md).

## Scope

The target is **Goggles 2**, not **DJI FPV Goggles V2**. Mobile DJI Virtual Flight support establishes an image-input path, but does not establish a generic PC display interface. Existing video-output projects and older-goggles modifications do not demonstrate input support for this model.

The first implementation milestone is a moving test image displayed in the goggles with measured latency. Simulator streaming comes after that milestone.

## Repository status

This repository is private. Agent context is intentionally tracked during research so it transfers between computers. Before making anything public, follow the [publication procedure](.agents/PUBLISHING.md); adding an ignore rule does not remove files from Git history.

The repository does not contain DJI installers, firmware, captures, or recovered proprietary code. Sources and download instructions are documented instead. This project is independent of DJI.
