---
date: 2025-12-03T00:00:00-08:00
researcher: Claude
git_commit: 4070c8cdb21ed3570c44748076071066be96d9fe
branch: master
repository: audacity
topic: "Audacity 4 Codebase Architecture and Stack Overview"
tags: [research, codebase, architecture, audacity, qt, qml, audio, effects, muse-framework]
status: complete
last_updated: 2025-12-03
last_updated_by: Claude
---

# Research: Audacity 4 Codebase Architecture and Stack Overview

**Date**: 2025-12-03
**Researcher**: Claude
**Git Commit**: 4070c8cdb21ed3570c44748076071066be96d9fe
**Branch**: master
**Repository**: audacity (fork from audacity/audacity)

## Research Question

How does this Audacity 4 codebase work, what does it do, and what is the technology stack?

## Summary

**Audacity** is an open-source, multi-track audio editor and recorder. This codebase represents **Audacity 4** - a major architectural rewrite currently in development. The key characteristics are:

1. **Hybrid Architecture**: AU4 wraps the complete Audacity 3.x codebase (`au3/`) while building a new modular architecture (`src/`)
2. **Muse Framework**: Built on a shared framework from MuseScore providing IoC/DI, UI components, and cross-platform abstractions
3. **Qt 6 / QML UI**: Modern declarative UI using Qt 6.2.4+ with QML for the interface
4. **Legacy Audio Engine**: Retains AU3's PortAudio-based audio engine with lock-free ring buffers
5. **Plugin Support**: VST3, LV2 (Linux), and Audio Units (macOS) through provider architecture

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Language** | C++17 |
| **Build System** | CMake 3.24+ |
| **UI Framework** | Qt 6.2.4+ / QML |
| **Audio I/O** | PortAudio |
| **Architecture** | Muse Framework (IoC/DI) |
| **Project Storage** | SQLite |
| **Platforms** | Windows, macOS, Linux |
| **License** | GPLv3 |

### Key Dependencies

- **PortAudio** - Cross-platform audio I/O
- **libsndfile** - Audio file format I/O
- **libsoxr** - High-quality sample rate conversion
- **SoundTouch/SBSMS** - Time-stretch and pitch-shift
- **SQLite** - Project file storage
- **FLAC, Vorbis, Opus, LAME, mpg123** - Audio codecs
- **VST3 SDK, LV2, AudioToolbox** - Plugin support

---

## Detailed Findings

### 1. Directory Structure

```
audacity/
├── src/                    # Audacity 4 new modular architecture
│   ├── app/               # Application entry point
│   ├── appshell/          # Main window, toolbars, navigation
│   ├── projectscene/      # Track timeline and waveform display
│   ├── playback/          # Playback control (wraps AU3)
│   ├── record/            # Recording control (wraps AU3)
│   ├── trackedit/         # Track/clip editing operations
│   ├── effects/           # Effects UI and plugin integration
│   ├── importexport/      # File import/export (wraps AU3)
│   ├── au3wrap/           # Bridge layer to AU3 code
│   ├── au3audio/          # Audio engine wrapper
│   └── context/           # Application state management
│
├── au3/                    # Audacity 3.x legacy code
│   ├── libraries/         # 40+ modular libraries
│   ├── src/               # Legacy application code
│   ├── modules/           # Import/export format modules
│   └── lib-src/           # Third-party libraries
│
├── muse_framework/         # MuseScore shared framework (submodule)
│   └── framework/         # IoC, UI, audio, actions, etc.
│
├── buildscripts/          # Platform packaging scripts
└── share/                 # Shared resources
```

### 2. Muse Framework Integration

The Muse Framework provides the architectural foundation:

**Enabled Modules** (`CMakeLists.txt:72-96`):
- `MUSE_MODULE_UI` - Qt/QML UI framework
- `MUSE_MODULE_ACTIONS` - Action dispatch system
- `MUSE_MODULE_SHORTCUTS` - Keyboard shortcuts
- `MUSE_MODULE_WORKSPACE` - Workspace management
- `MUSE_MODULE_ACCESSIBILITY` - Accessibility support
- `MUSE_MODULE_CLOUD` - Cloud integration
- `MUSE_MODULE_DIAGNOSTICS` - Crash reporting
- `MUSE_MODULE_AUDIOPLUGINS` - Plugin infrastructure

**Key Patterns**:

1. **Dependency Injection** via `muse::Inject<T>`:
```cpp
class PlaybackController {
    muse::Inject<IPlayer> m_player;
    muse::Inject<IActionsDispatcher> dispatcher;
};
```

2. **Module Lifecycle** via `IModuleSetup`:
```cpp
void AppShellModule::registerExports() {
    ioc()->registerExport<IAppShellConfiguration>(moduleName(), m_config);
}
```

3. **Interface Export** via `MODULE_EXPORT_INTERFACE` macro

### 3. Audio Engine Architecture

The audio system uses a **producer-consumer pattern** with lock-free ring buffers:

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Audio Thread  │────▶│  RingBuffer  │────▶│ PortAudio       │
│   (Mixer)       │     │  (lock-free) │     │ Callback Thread │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

**Key Files**:
- `au3/libraries/lib-audio-io/AudioIO.cpp` - PortAudio integration and callback
- `au3/libraries/lib-audio-io/RingBuffer.cpp` - Lock-free circular buffer
- `au3/libraries/lib-mixer/Mix.cpp` - Track mixing engine
- `src/au3audio/internal/au3audioengine.cpp` - AU4 wrapper

**Playback Flow**:
1. `PlaybackController` → `Au3Player::play()`
2. `Au3Player` → `Au3AudioEngine::startStream()`
3. `AudioIO::StartStream()` creates PortAudio stream
4. Audio thread fills RingBuffer via Mixer
5. PortAudio callback reads from RingBuffer → speakers

**Recording Flow**:
1. PortAudio callback captures input → RingBuffer
2. Audio thread drains buffer → `Sequence::Append()` → disk

### 4. Effects and Plugin System

**Architecture**: Provider-based with dual legacy/new implementations

**Built-in Effects** (`au3/libraries/lib-effects/LoadEffects.cpp`):
- Static registration via `BuiltinEffectsModule::Registration<T>`
- Examples: FadeIn, FadeOut, Reverse, Invert, StereoToMono

**Plugin Formats**:

| Format | Library | Platform |
|--------|---------|----------|
| VST3 | `lib-vst3/` | All |
| LV2 | `lib-lv2/` | Linux |
| Audio Unit | `lib-audio-unit/` | macOS |

**New Architecture** (`src/effects/`):
- `VstEffectsRepository` - VST effect metadata
- `Vst3PluginsScanner` - Plugin discovery
- `Vst3ViewLauncher` - Plugin UI integration

**Realtime Processing** (`au3/libraries/lib-realtime-effects/`):
- `RealtimeEffectManager` handles effect chains during playback
- `RealtimeEffectState` per-effect instance state
- Applied in audio callback: track effects → master effects

### 5. Qt/QML UI Layer

**Structure**:
```
DockWindow (WindowContent.qml)
├── MainToolBar
└── Pages
    ├── HomePage      → Project management
    ├── ProjectPage   → Main editing (primary)
    ├── PublishPage   → Publishing tools
    └── DevToolsPage  → Development utilities
```

**ProjectPage** (`src/appshell/qml/ProjectPage/ProjectPage.qml`) contains:
- **Toolbars**: Playback, Project, Undo/Redo, Workspaces
- **Panels**: TracksPanel (left), HistoryPanel (right), ChatPanel
- **Central**: TracksItemsView (timeline/waveforms)
- **StatusBar**: Selection status

**QML Registration** (`appshellmodule.cpp:144-187`):
```cpp
qmlRegisterType<ProjectPageModel>("Audacity.AppShell", 1, 0, "ProjectPageModel");
qmlRegisterType<PlaybackToolBarModel>("Audacity.ProjectScene", 1, 0, "PlaybackToolBarModel");
```

**Key QML Directories**:
- `src/appshell/qml/` - Main window, pages, preferences
- `src/projectscene/qml/Audacity/ProjectScene/` - Track display, toolbars

### 6. AU3/AU4 Integration

**Bridge Module**: `src/au3wrap/`

**Type Aliases** (`au3types.h`):
```cpp
using Au3Project = ::AudacityProject;
using Au3WaveTrack = ::WaveTrack;
using Au3WaveClip = ::WaveClip;
```

**Adapter Pattern**:
```cpp
class Au3Player : public IPlayer {
    void play() override {
        audioEngine()->startStream(sequences, options);
    }
};
```

**Key Adapters**:
| AU4 Interface | AU3 Implementation |
|---------------|-------------------|
| `IPlayer` | `Au3Player` |
| `IRecord` | `Au3Record` |
| `IExporter` | `Au3Exporter` |
| `IProjectHistory` | `Au3ProjectHistory` |
| `ITracksInteraction` | `Au3TracksInteraction` |

**Retained AU3 Libraries** (40+ modules):
- Audio: `lib-audio-io`, `lib-mixer`, `lib-realtime-effects`
- Tracks: `lib-wave-track`, `lib-label-track`, `lib-track`
- Effects: `lib-effects`, `lib-builtin-effects`, `lib-vst3`, `lib-lv2`
- DSP: `lib-math`, `lib-fft`, `lib-time-and-pitch`
- Project: `lib-project`, `lib-project-file-io`, `lib-project-history`

---

## Code References

### Entry Points
- `src/app/main.cpp:228-331` - Application bootstrap
- `src/appshell/qml/Main.qml:30-82` - Root QML window

### Audio Engine
- `au3/libraries/lib-audio-io/AudioIO.cpp:2572-2582` - PortAudio callback
- `au3/libraries/lib-audio-io/AudioIO.cpp:3160-3269` - Main audio callback
- `au3/libraries/lib-mixer/Mix.cpp` - Track mixing

### Module System
- `src/appshell/appshellmodule.cpp:97-114` - Export registration
- `muse_framework/framework/global/modularity/ioc.h` - IoC container

### UI
- `src/appshell/qml/ProjectPage/ProjectPage.qml:35-448` - Main editing page
- `src/projectscene/qml/Audacity/ProjectScene/tracksitemsview/TracksItemsView.qml` - Timeline

---

## Architecture Documentation

### Module Initialization Order

1. Framework modules (Diagnostics, AudioPlugins, UI, Actions...)
2. Audacity modules (AppShell, Context, Project, Playback...)
3. `registerExports()` - Register services in IoC
4. `resolveImports()` - Wire dependencies
5. `onPreInit()` / `onInit()` / `onAllInited()` - Lifecycle hooks

### Key Design Patterns

1. **IoC/Dependency Injection** - Services registered and resolved via `Inject<T>`
2. **Module System** - Features organized as independent modules with lifecycle
3. **Adapter Pattern** - AU4 interfaces wrap AU3 implementations
4. **Provider Pattern** - Plugin formats implement `PluginProvider`
5. **Lock-Free Audio** - Ring buffers for thread-safe audio data exchange
6. **Observer Pattern** - Event notifications between components

### Threading Model

| Thread | Purpose |
|--------|---------|
| Main/UI Thread | Qt event loop, QML rendering |
| Audio Thread | Mixer, buffer filling |
| PortAudio Callback | Real-time audio I/O (lock-free) |
| Plugin Scanner | Background plugin discovery |

---

## Related Research

This is the initial codebase overview. Future research could explore:
- Specific effect implementation details
- Project file format (SQLite schema)
- Plugin sandboxing architecture
- Spectrogram rendering pipeline

---

## Open Questions

1. How will the new `src/chat/` module integrate with the audio workflow?
2. What is the migration path for wxWidgets-dependent AU3 code?
3. How does the workspace system persist layout configurations?
