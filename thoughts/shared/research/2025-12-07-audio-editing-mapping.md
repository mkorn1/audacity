---
date: 2025-12-07T07:32:40Z
researcher: michaelkorn
git_commit: 137cda110d141e935211e7b6e615f6d245d71521
branch: master
repository: audacity
topic: "Complete Mapping of Audio Editing Capabilities in Audacity"
tags: [research, codebase, audio-editing, effects, clips, tracks, undo, menus, playback]
status: complete
last_updated: 2025-12-07
last_updated_by: michaelkorn
---

# Research: Complete Mapping of Audio Editing Capabilities in Audacity

**Date**: 2025-12-07T07:32:40Z
**Researcher**: michaelkorn
**Git Commit**: 137cda110d141e935211e7b6e615f6d245d71521
**Branch**: master
**Repository**: audacity

## Research Question

Provide a mapping of all the ways audio can be edited in Audacity. Provide a thorough report of each function, how it is used by the user, what can be changed, what that does, how the backend calls it, how it is stored, etc.

## Summary

Audacity has a **dual-layer architecture** for audio editing:
1. **AU3 Layer** (`/au3/`) - Original Audacity 3.x codebase with wxWidgets UI and direct implementations
2. **Audacity 4 Layer** (`/src/`) - Modern modular architecture using Muse Framework with QML UI and interface-based design

Audio editing capabilities fall into these major categories:
- **Effects Processing** - Transform audio with built-in and plugin effects
- **Clip Operations** - Cut, copy, paste, split, trim, delete audio regions
- **Selection** - Time and track selection for targeted operations
- **Real-Time Processing** - Non-destructive effect chains during playback
- **Time/Pitch Manipulation** - Stretch, compress, and pitch-shift audio
- **Track Management** - Create, delete, mix, and organize audio tracks

---

## Detailed Findings

### 1. Effects System

#### Overview
Effects transform audio data by processing samples through algorithms. They can be **destructive** (modify stored audio) or **real-time** (applied during playback only).

#### User Interaction
- **Menu Access**: Effect menu lists all available effects organized by category
- **Keyboard Shortcuts**: Configurable via `src/app/configs/data/shortcuts.xml`
- **Context Menu**: Right-click on selected audio region
- **Real-Time Panel**: Track effects panel for non-destructive effects

#### Built-in Effects

| Effect | What It Does | Key Parameters | Implementation File |
|--------|-------------|----------------|---------------------|
| **Amplify** | Increase/decrease volume | Amplification (dB), Allow clipping | `src/effects/builtin/amplify/amplifyeffect.cpp` |
| **Normalize** | Set peak level to target | Peak level, DC offset removal | `src/effects/builtin/normalize/normalizeeffect.cpp` |
| **Fade In/Out** | Gradual volume change | Duration (from selection) | `src/effects/builtin/fade/fadeeffect.cpp` |
| **Compressor** | Dynamic range compression | Threshold, Ratio, Attack, Release, Knee | `src/effects/builtin/dynamics/compressor/compressoreffect.cpp` |
| **Limiter** | Prevent clipping | Threshold, Release | `src/effects/builtin/dynamics/limiter/limitereffect.cpp` |
| **Reverb** | Add room ambience | Room size, Damping, Wet/Dry | `src/effects/builtin/reverb/reverbeffect.cpp` |
| **Change Pitch** | Alter pitch without tempo | Semitones, Percent | `src/effects/builtin/changepitch/changepitcheffect.cpp` |
| **Noise Reduction** | Remove background noise | Noise profile, Reduction amount | `src/effects/builtin/noisereduction/noisereductioneffect.cpp` |
| **Click Removal** | Remove clicks/pops | Threshold, Max spike width | `src/effects/builtin/clickremoval/clickremovaleffect.cpp` |
| **Truncate Silence** | Remove silent sections | Threshold, Duration | `src/effects/builtin/truncatesilence/truncatesilenceeffect.cpp` |
| **Invert** | Phase inversion | None | `src/effects/builtin/invert/inverteffect.cpp` |
| **Reverse** | Play backward | None | `src/effects/builtin/reverse/reverseeffect.cpp` |
| **Repair** | Fix small audio glitches | Selection only (<128 samples) | `src/effects/builtin/repair/repaireffect.cpp` |

#### Plugin Systems

| Format | Platform | Scanner | Repository |
|--------|----------|---------|------------|
| **VST3** | All | `src/effects/vst/internal/vst3pluginsscanner.cpp` | `src/effects/vst/internal/vsteffectsrepository.cpp` |
| **LV2** | Linux/Mac | `src/effects/lv2/internal/lv2pluginsscanner.cpp` | `src/effects/lv2/internal/lv2effectsrepository.cpp` |
| **Audio Unit** | macOS | `src/effects/audio_unit/internal/audiounitpluginsscanner.cpp` | `src/effects/audio_unit/internal/audiouniteffectsrepository.cpp` |
| **Nyquist** | All | Built-in | `src/effects/nyquist/internal/nyquisteffectsrepository.cpp` |
| **LADSPA** | Linux | Legacy AU3 | `au3/libraries/lib-ladspa/` |

#### Backend Effect Execution Flow

```
User selects region → Menu/Shortcut triggers action
    ↓
IActionsDispatcher::dispatch("effect-apply", effectId)
    ↓
EffectsActionsController::onAction()
    ↓
IEffectExecutionScenario::performEffect()
    ↓
Effect::Process() - iterates over samples
    ↓
WaveTrack::SetSamples() - writes modified data
    ↓
UndoManager::PushState() - saves for undo
```

**Key Files:**
- Effect execution: `src/effects/effects_base/internal/effectexecutionscenario.cpp`
- Effect registration: `src/effects/builtin/internal/builtineffectsrepository.cpp`
- Effect UI: `src/effects/effects_base/view/effectsuiengine.cpp`

---

### 2. Clip Operations

#### Overview
Clips are segments of audio within a track. Operations modify clip boundaries, positions, or content.

#### User Operations

| Operation | User Action | Backend Call | What Changes |
|-----------|------------|--------------|--------------|
| **Cut** | Ctrl+X / Edit→Cut | `Au3ClipsInteraction::cutClipIntoClipboard()` | Removes selection, copies to clipboard |
| **Copy** | Ctrl+C / Edit→Copy | `Au3TrackEditClipboard::copy()` | Copies selection to clipboard |
| **Paste** | Ctrl+V / Edit→Paste | `Au3TrackEditClipboard::paste()` | Inserts clipboard at cursor |
| **Delete** | Delete / Edit→Delete | `Au3ClipsInteraction::removeClip()` | Removes selection, no clipboard |
| **Split** | Ctrl+I / Edit→Split | `Au3ClipsInteraction::splitAt()` | Divides clip at cursor |
| **Split Cut** | Ctrl+Alt+X | `Au3ClipsInteraction::splitCutSelectedIntoClipboard()` | Cut without ripple |
| **Split Delete** | Ctrl+Alt+K | `Au3ClipsInteraction::splitDeleteSelected()` | Delete without ripple |
| **Trim** | Drag clip edges | `WaveClipAdjustBorderHandle::Drag()` | Adjusts clip start/end |
| **Move** | Drag clip body | `TimeShiftHandle::Drag()` | Changes clip position |
| **Duplicate** | Ctrl+D | `Au3ClipsInteraction::duplicateClip()` | Creates copy at position |
| **Join** | Ctrl+J | `Au3ClipsInteraction::mergeSelectedOnTrack()` | Combines adjacent clips |

#### Clip Data Structure

```cpp
// au3/libraries/lib-wave-track/WaveClip.h
class WaveClip {
    Sequence mSequence;      // Raw audio samples
    Envelope mEnvelope;      // Volume automation
    double mTrimLeft;        // Left trim offset
    double mTrimRight;       // Right trim offset
    double mClipStretchRatio; // Time stretch factor
    int mCentShift;          // Pitch shift (cents)
    wxString mName;          // Clip label
};
```

#### Backend Implementation
- Interface: `src/trackedit/iclipsinteraction.h`
- AU3 Bridge: `src/trackedit/internal/au3/au3clipsinteraction.cpp`
- Actions Controller: `src/trackedit/internal/trackeditactionscontroller.cpp`

---

### 3. Selection System

#### Selection Types

| Type | What It Selects | Storage | User Action |
|------|----------------|---------|-------------|
| **Time Selection** | Time range (start→end) | `SelectedRegion` | Click+drag on timeline/waveform |
| **Track Selection** | Entire track(s) | `SelectionState` | Click track panel |
| **Clip Selection** | Individual clip(s) | Clip affordance state | Click on clip |
| **Spectral Selection** | Frequency range | `SelectedRegion` (f0, f1) | Ctrl+drag in spectrogram view |

#### Selection Data Storage

```cpp
// au3/libraries/lib-time-frequency-selection/SelectedRegion.h
class SelectedRegion {
    double mT0, mT1;     // Time range (seconds)
    double mF0, mF1;     // Frequency range (Hz) - spectral selection
};

// au3/libraries/lib-track-selection/SelectionState.h
class SelectionState {
    TrackIdSet mSelectedTracks;  // Set of selected track IDs
};
```

#### Selection Backend
- Selection Controller: `src/trackedit/internal/au3/au3selectioncontroller.cpp`
- View Info: `au3/libraries/lib-time-frequency-selection/ViewInfo.cpp`
- UI Rendering: `src/projectscene/view/tracksitemsview/selectionviewcontroller.cpp`

---

### 4. Real-Time Effects (Non-Destructive)

#### Overview
Real-time effects are applied during playback without modifying stored audio data. They can be added per-track or to the master output.

#### User Interaction
- **Track Effects Panel**: Shows effect chain for selected track
- **Add Effect**: Click "+" button → select from menu
- **Bypass**: Toggle effect on/off
- **Reorder**: Drag effects in chain
- **Edit Parameters**: Double-click effect

#### Backend Architecture

```
Playback Request
    ↓
AudioIO::StartStream()
    ↓
RealtimeEffectManager::ProcessStart()
    ↓
For each audio buffer:
    RealtimeEffectList::ForEach(state → state.Process(buffer))
    ↓
EffectStage::Process() - applies effect chain
    ↓
Output to audio device
```

**Key Files:**
- Manager: `au3/libraries/lib-realtime-effects/RealtimeEffectManager.cpp`
- State: `au3/libraries/lib-realtime-effects/RealtimeEffectState.cpp`
- Effect Stage: `au3/libraries/lib-mixer/EffectStage.cpp`
- Service: `src/effects/effects_base/internal/realtimeeffectservice.cpp`

---

### 5. Audio Data Storage

#### Storage Hierarchy

```
Project (.aup3 SQLite file)
├── TrackList
│   └── WaveTrack (multiple)
│       └── WaveClip (multiple per track)
│           ├── Sequence (raw audio)
│           │   └── SampleBlock (multiple, stored in SQLite)
│           ├── Envelope (volume automation)
│           └── Metadata (name, color, pitch shift, etc.)
```

#### Sample Storage (AUP3 Format)

```cpp
// au3/libraries/lib-project-file-io/SqliteSampleBlock.cpp
// Audio samples stored as BLOBs in SQLite database

// Block structure:
// - blockid: unique identifier
// - sampleformat: 16-bit, 24-bit, or 32-bit float
// - summin, summax, sumrms: summary statistics for waveform display
// - samples: raw audio data BLOB
```

#### Sample Formats
Defined in `au3/libraries/lib-math/SampleFormat.h`:
- `int16Sample` - 16-bit integer (-32768 to 32767)
- `int24Sample` - 24-bit integer
- `floatSample` - 32-bit floating point (-1.0 to 1.0)

#### Key Data Files
- Project I/O: `au3/libraries/lib-project-file-io/ProjectFileIO.cpp`
- Sequence: `au3/libraries/lib-wave-track/Sequence.cpp`
- Sample Block: `au3/libraries/lib-wave-track/SampleBlock.cpp`
- Wave Track: `au3/libraries/lib-wave-track/WaveTrack.cpp`

---

### 6. Time/Pitch Manipulation

#### Overview
Time stretching and pitch shifting modify playback rate and pitch independently using the SoundTouch library.

#### User Operations

| Operation | What It Does | Parameters | Implementation |
|-----------|-------------|------------|----------------|
| **Clip Stretch** | Change duration | Stretch ratio | Drag stretch handles on clip |
| **Change Tempo** | Speed up/slow down | BPM or % | Effect menu |
| **Change Pitch** | Transpose | Semitones/cents | Effect menu |
| **Change Speed** | Both tempo+pitch | % change | Effect menu |
| **Paulstretch** | Extreme stretch | Factor (10x+) | Effect menu |

#### Backend Implementation

```cpp
// au3/libraries/lib-stretching-sequence/ClipTimeAndPitchSource.cpp
// Provides time-stretched/pitch-shifted samples for playback

// Uses SoundTouch library:
// au3/lib-src/soundtouch/source/SoundTouch/
// - TDStretch.cpp: Time-domain stretching algorithm
// - RateTransposer.cpp: Sample rate transposition for pitch
```

**Key Files:**
- Stretching Sequence: `au3/libraries/lib-stretching-sequence/StretchingSequence.cpp`
- Time/Pitch Source: `au3/libraries/lib-stretching-sequence/ClipTimeAndPitchSource.cpp`
- SoundTouch Integration: `au3/lib-src/soundtouch/`

---

### 7. Undo/Redo System

#### Architecture
Two parallel undo systems exist:
1. **Modern** (`src/trackedit/internal/undomanager.cpp`) - Interface-based
2. **Legacy** (`au3/libraries/lib-project-history/UndoManager.cpp`) - Direct implementation

#### How Undo States Are Stored

```cpp
// au3/libraries/lib-project-history/UndoManager.cpp
struct UndoState {
    std::shared_ptr<TrackList> tracks;  // Complete track list snapshot
    SelectedRegion selectedRegion;       // Selection state
    wxString description;                // "Amplify", "Delete", etc.
};

// States stored in a stack:
std::vector<UndoState> mUndoStates;
size_t mCurrent;  // Current position in history
```

#### Undo Trigger Flow

```
User performs edit (e.g., Apply Effect)
    ↓
ProjectHistory::PushState("Effect Name")
    ↓
UndoManager::PushState()
    ↓
Creates snapshot of TrackList
    ↓
Adds to undo stack

User presses Ctrl+Z
    ↓
UndoManager::Undo()
    ↓
Restores previous TrackList state
    ↓
UI refreshes to show restored state
```

---

### 8. Menu & Command System

#### Dual Architecture

| System | Location | Used By |
|--------|----------|---------|
| **Modern (Muse)** | `muse_framework/framework/actions/` | Audacity 4 UI |
| **Legacy (AU3)** | `au3/libraries/lib-menus/` | AU3 components |

#### Action Dispatch Flow (Modern)

```
User triggers action (menu/shortcut/toolbar)
    ↓
IActionsDispatcher::dispatch(actionCode, args)
    ↓
ActionsDispatcher finds registered handler
    ↓
Module's ActionController::onAction()
    ↓
Executes specific operation
```

#### Menu Definitions

| Menu | AU3 File | What It Contains |
|------|----------|------------------|
| File | `au3/src/menus/FileMenus.cpp` | Open, Save, Export, Import |
| Edit | `au3/src/menus/EditMenus.cpp` | Cut, Copy, Paste, Undo, Redo |
| Select | `au3/src/menus/SelectMenus.cpp` | Selection operations |
| View | `au3/src/menus/ViewMenus.cpp` | Zoom, Show/Hide panels |
| Transport | `au3/src/menus/TransportMenus.cpp` | Play, Stop, Record, Loop |
| Track | `au3/src/menus/TrackMenus.cpp` | Add, Remove, Mix tracks |
| Effect | `au3/src/menus/PluginMenus.cpp` | All effect plugins |
| Clip | `au3/src/menus/ClipMenus.cpp` | Clip-specific operations |

---

### 9. Audio I/O and Playback

#### Playback Architecture

```
User presses Play
    ↓
PlaybackController::play()
    ↓
Au3Player::play()
    ↓
AudioIO::StartStream()
    ↓
Creates playback thread
    ↓
Mix::Process() - reads from tracks, applies effects
    ↓
PortAudio callback - sends to audio device
```

#### Recording Architecture

```
User presses Record
    ↓
RecordController::start()
    ↓
Au3Record::start()
    ↓
AudioIO::StartStream(withRecording=true)
    ↓
PortAudio callback receives audio
    ↓
WaveTrackSink::Write() - writes to new track
    ↓
Sequence::Append() - adds sample blocks
```

**Key Files:**
- Audio I/O: `au3/libraries/lib-audio-io/AudioIO.cpp`
- Mixer: `au3/libraries/lib-mixer/Mix.cpp`
- Playback: `src/playback/internal/au3/au3player.cpp`
- Recording: `src/record/internal/au3/au3record.cpp`

---

## Code References

### Effects
- `src/effects/effects_base/internal/effectexecutionscenario.cpp` - Effect execution
- `src/effects/builtin/internal/builtineffectsrepository.cpp` - Effect registration
- `au3/libraries/lib-effects/Effect.cpp` - Base effect class

### Clips
- `src/trackedit/internal/au3/au3clipsinteraction.cpp` - Clip operations
- `au3/libraries/lib-wave-track/WaveClip.cpp` - Clip data structure
- `au3/libraries/lib-wave-track/Sequence.cpp` - Audio sample storage

### Selection
- `src/trackedit/internal/au3/au3selectioncontroller.cpp` - Selection controller
- `au3/libraries/lib-time-frequency-selection/SelectedRegion.cpp` - Time selection
- `au3/libraries/lib-track-selection/SelectionState.cpp` - Track selection

### Undo/History
- `au3/libraries/lib-project-history/UndoManager.cpp` - Undo manager
- `src/trackedit/internal/au3/au3projecthistory.cpp` - Project history bridge

### Menus/Actions
- `muse_framework/framework/actions/internal/actionsdispatcher.cpp` - Action dispatcher
- `src/trackedit/internal/trackeditactionscontroller.cpp` - Track edit actions
- `au3/src/menus/EditMenus.cpp` - Edit menu definitions

### Audio I/O
- `au3/libraries/lib-audio-io/AudioIO.cpp` - Audio engine
- `au3/libraries/lib-mixer/Mix.cpp` - Mixing pipeline
- `src/playback/internal/au3/au3player.cpp` - Playback control

### Storage
- `au3/libraries/lib-project-file-io/ProjectFileIO.cpp` - Project file management
- `au3/libraries/lib-project-file-io/SqliteSampleBlock.cpp` - Sample storage

---

## Architecture Documentation

### Dual-Layer Design Pattern
The codebase follows a consistent pattern:
1. **Interface** (`i*.h`) - Defines the contract
2. **AU3 Implementation** (`au3*.cpp`) - Bridges to legacy code
3. **Modern UI** (QML) - Uses interfaces through models

Example:
```
IClipsInteraction (interface)
    ↓
Au3ClipsInteraction (implementation using AU3 code)
    ↓
ClipContextMenuModel (QML binding)
```

### Module Structure
Each feature module follows:
```
src/{module}/
├── {module}module.h/.cpp     # Module registration
├── i{feature}.h              # Interfaces
├── internal/
│   ├── {feature}controller.cpp
│   └── au3/                  # AU3 bridge implementations
├── view/
│   └── {feature}model.cpp    # QML view models
└── qml/                      # QML UI files
```

---

## Open Questions

1. **Effect Preset Storage**: How are effect presets serialized and where are they stored?
2. **Plugin Scanning Cache**: Where is the scanned plugin database cached?
3. **Real-time Effect Persistence**: How are real-time effect chains saved/restored with projects?
4. **Spectral Editing**: Full implementation details of spectral selection operations

---

## Related Research

- Effect view architecture documentation: `docs/effect-view-architecture.md`
- Effect framework documentation: `au3/libraries/lib-audacity-application-logic/effect-framework.md`
