---
date: 2025-12-08T02:22:48Z
researcher: michaelkorn
git_commit: 1f8d5e5b7811dfc3c68e9505e1bd3f3973745b34
branch: master
repository: audacity
topic: "Audacity Podcast Fork Status - AI Assistant and Transcription Features"
tags: [research, codebase, chat, transcription, ai-assistant, podcast]
status: complete
last_updated: 2025-12-08
last_updated_by: michaelkorn
---

# Research: Audacity Podcast Fork Status - AI Assistant and Transcription Features

**Date**: 2025-12-08T02:22:48Z
**Researcher**: michaelkorn
**Git Commit**: 1f8d5e5b7811dfc3c68e9505e1bd3f3973745b34
**Branch**: master
**Repository**: audacity

## Research Question
What is the status of our Audacity fork for podcasters? We have some AI assistant functionality and a transcription tool and renderer.

## Summary

This Audacity fork ("WTFork") adds significant podcast-focused features on top of the standard Audacity audio editor. The key additions are:

1. **AI Chat Assistant** - A fully functional conversational interface using OpenAI's GPT models with function calling to control Audacity
2. **Audio Transcription** - AssemblyAI-powered speech-to-text with word-level timestamps and filler word detection
3. **Transcript Renderer** - Visual display of transcribed words synchronized with the audio timeline

The system is **functional and actively developed**, with recent commits (last 5) showing work on transcription rendering, looping logic, and chat functionality.

## Detailed Findings

### 1. AI Chat Assistant

#### Architecture
The chat assistant uses a 3-layer architecture:
- **QML UI Layer**: Chat sidebar with message display, input, and approval panels
- **C++ Bridge Layer**: Python process management and JSON communication
- **Python AI Backend**: OpenAI integration, tool orchestration, and state management

#### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| ChatSidebar.qml | `src/chat/qml/Audacity/Chat/ChatSidebar.qml` | Main chat UI container |
| ChatViewModel | `src/chat/view/chatviewmodel.cpp` | QML-C++ data binding |
| PythonBridge | `src/chat/internal/pythonbridge.cpp` | C++/Python IPC |
| Orchestrator | `src/chat/python/orchestrator.py` | OpenAI function calling |
| Tools | `src/chat/python/tools.py` | Audio editing tool implementations |

#### Available Tool Categories
- **Selection Tools**: Time selection, select all, select tracks
- **Track Tools**: Create, delete, duplicate tracks
- **Clip Tools**: Split, join, trim, silence clips
- **Editing Tools**: Cut, copy, paste, undo, redo
- **Effect Tools**: Noise reduction, normalize, amplify, fades, compression
- **Playback Tools**: Play, stop, pause, seek
- **Label Tools**: Add labels at timestamps
- **Transcription Tools**: Transcribe audio, search transcript, find filler words
- **State Query Tools**: Read-only project state access

#### Approval Workflow
Destructive operations (cut, delete, effects) require user approval:
- ApprovalPanel shows operation preview
- Supports step-by-step or batch approval mode
- Undo buttons appear on completed operations

#### Configuration
Requires environment variables:
- `OPENAI_API_KEY` - For GPT function calling (falls back to keyword matching without it)
- `ASSEMBLYAI_API_KEY` - For audio transcription

### 2. Transcription System

#### Service Pipeline
1. User requests transcription via chat
2. C++ exports audio tracks to temporary WAV file
3. Python uploads to AssemblyAI API
4. AssemblyAI returns word-level timestamps with filler word flags
5. JSON converted to C++ Transcript objects
6. TranscriptService stores and broadcasts to listeners

#### Data Model (`src/chat/dom/transcript.h`)
```cpp
struct TranscriptWord {
    muse::String word;      // The text
    double startTime;       // Start timestamp (seconds)
    double endTime;         // End timestamp (seconds)
    double confidence;      // 0.0-1.0 accuracy score
    bool isFiller;          // um, uh, like, you know, etc.
    std::optional<muse::String> speaker;  // Speaker diarization
};
```

#### Key Files
| File | Purpose |
|------|---------|
| `src/chat/python/transcription_service.py` | AssemblyAI API integration |
| `src/chat/internal/transcriptservice.cpp` | C++ transcript storage |
| `src/chat/internal/transcriptjsonconverter.cpp` | JSON-to-C++ conversion |

### 3. Transcript Renderer

#### Visual Approach
Transcribed words appear as interactive bubbles above the audio timeline:
- Words positioned by their timestamp relative to timeline zoom
- Filler words highlighted with different background color (gray vs light gray)
- Click a word to seek playhead to that timestamp

#### Rendering Components
| Component | Location | Role |
|-----------|----------|------|
| TranscriptContainer.qml | `src/projectscene/qml/.../TranscriptContainer.qml` | QML container with Repeater |
| TranscriptListModel | `src/projectscene/view/.../transcriptlistmodel.cpp` | Qt model for visible words |
| TranscriptWordItem | `src/projectscene/view/.../transcriptworditem.cpp` | Individual word data |

#### Performance Optimizations
- **Viewport culling**: Only loads words within visible time range plus cache buffer
- **Adaptive detail**: Switches from word-level to utterance-level when zoomed out (>5s visible)
- **Lazy reloading**: Only refetches when scrolled outside cached range

#### Timeline Synchronization
- `TimelineContext` provides `timeToPosition()` for pixel calculations
- Words reposition automatically when zoom or scroll changes
- QML property bindings ensure smooth updates

### 4. Integration Points

#### Main Application
- `src/appshell/qml/ProjectPage/ProjectPage.qml` - Integrates ChatSidebar
- `src/projectscene/qml/.../TracksItemsView.qml` - Integrates TranscriptContainer at `y: root.height - 30`

#### Module Registration
- `src/chat/chatmodule.cpp` - Registers chat and transcript services
- `src/projectscene/projectscenemodule.cpp` - Registers transcript UI components

## Code References

### Chat System
- `src/chat/qml/Audacity/Chat/ChatSidebar.qml:24-48` - Chat layout structure
- `src/chat/view/chatviewmodel.cpp:70-85` - Send message implementation
- `src/chat/internal/pythonbridge.cpp:364-420` - JSON IPC protocol
- `src/chat/python/orchestrator.py:77-97` - OpenAI function calling
- `src/chat/python/tools.py:982-1242` - Tool registry

### Transcription
- `src/chat/python/transcription_service.py:190-287` - AssemblyAI upload and poll
- `src/chat/internal/pythonbridge.cpp:549-556` - Transcript data handling
- `src/chat/dom/transcript.h:12-38` - Data structures

### Renderer
- `src/projectscene/qml/.../TranscriptContainer.qml:100-186` - Word bubble delegate
- `src/projectscene/view/.../transcriptlistmodel.cpp:112-195` - Model update logic
- `src/projectscene/view/.../transcriptlistmodel.cpp:223-224` - Position calculation

## Architecture Documentation

### Communication Flow
```
User Input → ChatInput.qml → ChatViewModel → ChatController → PythonBridge
                                                                   ↓
                                                          Python Process
                                                                   ↓
                                                            Orchestrator
                                                                   ↓
                                                            OpenAI API
                                                                   ↓
                                                         Tool Execution
                                                                   ↓
PythonBridge → ChatController → ChatViewModel → ChatMessageList.qml
```

### Design Patterns
- **Model-View-ViewModel**: QML ↔ C++ ViewModels ↔ Services
- **Dependency Injection**: `muse::Inject<IService>` pattern throughout
- **Observer Pattern**: Async channels for state change notifications
- **Bridge Pattern**: Python subprocess with JSON protocol

## Current Development Status

### Working Features
- Chat message exchange
- OpenAI function calling with TOOL_DEFINITIONS
- Full tool execution suite
- Approval workflow with batch mode
- Undo integration
- Audio transcription via AssemblyAI
- Filler word detection
- Transcript word rendering on timeline
- Click-to-seek from transcript words

### In-Progress (Based on Recent Commits)
1. **Transcript word positioning** - Debug borders still visible in TranscriptContainer.qml
2. **Transcript word tracking** - Recent commit "transcribed words tracking better"
3. **Looping playback** - Recent commit on looping logic and state changes

### Test Coverage
- 18 Python test files in `src/chat/python/tests/`
- Covers: intent planning, state management, tool prerequisites, error handling
- C++ playback tests in `src/playback/tests/`

## Related Research
- `thoughts/shared/plans/2025-12-07-podcast-copilot-analysis-features.md`
- `thoughts/shared/plans/2025-12-06-state-preparation-architecture.md`
- `src/chat/IMPLEMENTATION_PLAN.md`
- `src/chat/python/README.md`

## Open Questions

1. **Transcript persistence** - Are transcripts saved with the project file?
2. **Multi-track transcription** - How does it handle multiple speakers on different tracks?
3. **Offline transcription** - Is there a fallback when AssemblyAI is unavailable (Whisper local)?
4. **Speaker diarization** - Is the speaker field in TranscriptWord being used?
