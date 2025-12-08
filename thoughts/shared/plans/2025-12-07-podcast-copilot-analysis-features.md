# Podcast Copilot Analysis Features Implementation Plan

## Overview

Implement three analysis-driven features for the AI chat copilot, specifically targeting podcast editing workflows:

1. **Silence Detection + Preview** - Detect silence regions and show them before removal
2. **Loudness Analysis + Multi-Track Leveling** - Analyze LUFS per track and suggest/apply normalization
3. **Semantic Selection via Transcription** - Transcribe audio with CrisperWhisper API, find filler words and specific phrases

The key UX principle: **analyze first, show results, let user approve before acting**.

## Current State Analysis

### What Exists

**AI Chat Infrastructure** (`src/chat/`):
- Python orchestrator with OpenAI function calling
- C++ ↔ Python bridge via stdin/stdout JSON
- Tool execution through `IAgentActionExecutor`
- State queries through `IAgentStateReader`
- Approval workflow UI (ApprovalPanel, PreviewPanel)

**Silence Detection** (`au3/libraries/lib-builtin-effects/TruncSilenceBase`):
- `Analyze()` method is **public** - can detect without removing
- Returns `RegionList` with `(start, end)` in seconds
- Configurable threshold (-80 to -20 dB) and min duration

**Loudness Analysis** (`au3/libraries/lib-math/EBUR128`):
- Full EBU R128 LUFS measurement with K-weighting
- Used by NormalizeLoudness effect (two-pass: analyze then process)
- No standalone analysis API exposed

**Timeline Visualization** (`src/projectscene/`):
- Track items view with clip rendering
- Selection visualization controller
- No mechanism for temporary "analysis result" overlays

### Key Discoveries

- `TruncSilenceBase::Analyze()` at `au3/libraries/lib-builtin-effects/TruncSilenceBase.h:58` - public method for silence detection
- `EBUR128::IntegrativeLoudness()` at `au3/libraries/lib-math/EBUR128.cpp:115` - returns linear loudness value
- `IAgentStateReader` at `src/chat/iagentstatereader.h` - existing interface for state queries
- Current state queries defined in `src/chat/internal/agentstatereader.cpp`

## Desired End State

After implementation:

1. User says "Find all the long pauses" → AI detects silences → shows list in chat + highlights on timeline → user approves which to remove
2. User says "Check the levels on each track" → AI analyzes LUFS per track → shows comparison → suggests normalization targets
3. User says "Find where I said 'um'" → AI transcribes → shows all occurrences with timestamps → user can navigate/select/delete

Verification:
- New state query tools work: `detect_silences`, `analyze_loudness`, `transcribe_audio`, `search_transcript`
- Timeline shows temporary highlight overlays for analysis results
- Chat shows clickable results that navigate timeline
- Approval workflow allows selective action on detected regions

## What We're NOT Doing

- Building a full transcript editor UI (like Descript)
- Real-time transcription during recording
- Speaker diarization (identifying who said what)
- Local model hosting for transcription (API-only for now)
- Automatic filler word removal without user approval

---

## Implementation Approach

### High-Level Architecture

```
User Request ("find silences")
    ↓
Python Orchestrator (intent parsing)
    ↓
State Query Tool (detect_silences)
    ↓
C++ AgentStateReader → TruncSilenceBase::Analyze()
    ↓
Results returned to Python as JSON
    ↓
Python formats response + creates preview data
    ↓
Chat UI shows results + Timeline shows overlays
    ↓
User approves action → Execute removal
```

### New Components

1. **C++ Analysis APIs** - Extend `IAgentStateReader` with analysis methods
2. **Python Analysis Tools** - New tools in `tool_schemas.py` and `tools.py`
3. **Timeline Overlay System** - Temporary visual markers for analysis results
4. **Transcription Service** - Python module calling CrisperWhisper API
5. **Enhanced Chat Results** - Clickable results with timeline navigation

---

## Phase 1: Silence Detection Infrastructure

### Overview
Expose the existing silence detection algorithm as a state query, add timeline visualization for detected regions.

### Changes Required

#### 1.1 Extend IAgentStateReader Interface

**File**: `src/chat/iagentstatereader.h`
**Changes**: Add method for silence detection

```cpp
// Add to IAgentStateReader interface
struct SilenceRegion {
    double startTime;
    double endTime;
    double durationSeconds;
};

virtual std::vector<SilenceRegion> detectSilences(
    double thresholdDb = -40.0,
    double minDurationSeconds = 0.5,
    std::optional<double> startTime = std::nullopt,
    std::optional<double> endTime = std::nullopt
) const = 0;
```

#### 1.2 Implement Silence Detection in AgentStateReader

**File**: `src/chat/internal/agentstatereader.cpp`
**Changes**: Implement the detection using TruncSilenceBase::Analyze()

```cpp
std::vector<SilenceRegion> AgentStateReader::detectSilences(
    double thresholdDb,
    double minDurationSeconds,
    std::optional<double> startTime,
    std::optional<double> endTime
) const
{
    // Get project and tracks
    auto project = globalContext()->currentProject();
    if (!project) return {};

    auto& trackList = TrackList::Get(project->au3Project());

    // Configure TruncSilence parameters
    TruncSilenceBase silenceDetector;
    silenceDetector.mThresholdDB = thresholdDb;
    silenceDetector.mInitialAllowedSilence = minDurationSeconds;

    // Set time range
    double t0 = startTime.value_or(0.0);
    double t1 = endTime.value_or(project->totalTime());

    // Detect silences across all wave tracks
    RegionList silences;
    // ... call Analyze() for each track, intersect results ...

    // Convert to return format
    std::vector<SilenceRegion> result;
    for (const auto& region : silences) {
        result.push_back({
            region.start,
            region.end,
            region.end - region.start
        });
    }
    return result;
}
```

#### 1.3 Add State Query Handler

**File**: `src/chat/internal/pythonbridge.cpp`
**Changes**: Handle `detect_silences` query type in the JSON protocol

```cpp
// In handleStateQuery():
if (queryType == "detect_silences") {
    double threshold = params.value("threshold_db", -40.0);
    double minDuration = params.value("min_duration", 0.5);
    auto startTime = params.contains("start_time")
        ? std::optional(params["start_time"].get<double>())
        : std::nullopt;
    auto endTime = params.contains("end_time")
        ? std::optional(params["end_time"].get<double>())
        : std::nullopt;

    auto regions = m_stateReader->detectSilences(threshold, minDuration, startTime, endTime);

    json result;
    result["success"] = true;
    result["regions"] = json::array();
    for (const auto& r : regions) {
        result["regions"].push_back({
            {"start_time", r.startTime},
            {"end_time", r.endTime},
            {"duration", r.durationSeconds}
        });
    }
    return result;
}
```

#### 1.4 Add Python Tool Definition

**File**: `src/chat/python/tool_schemas.py`
**Changes**: Add detect_silences tool

```python
{
    "type": "function",
    "function": {
        "name": "detect_silences",
        "description": "Detect silent regions in the audio. Returns a list of time ranges where audio is below the threshold. Use this to find pauses, gaps, or silence to remove.",
        "parameters": {
            "type": "object",
            "properties": {
                "threshold_db": {
                    "type": "number",
                    "description": "Volume threshold in dB. Audio below this is considered silence. Default -40 dB. Range: -80 to -20."
                },
                "min_duration": {
                    "type": "number",
                    "description": "Minimum silence duration in seconds to detect. Default 0.5. Shorter silences are ignored."
                },
                "start_time": {
                    "type": "number",
                    "description": "Start of region to analyze (seconds). Omit to start from beginning."
                },
                "end_time": {
                    "type": "number",
                    "description": "End of region to analyze (seconds). Omit to analyze to end."
                }
            },
            "required": []
        }
    }
}
```

#### 1.5 Add Python Tool Implementation

**File**: `src/chat/python/tools.py`
**Changes**: Add StateQueryTools method and ToolRegistry mapping

```python
# In StateQueryTools class:
def detect_silences(self, threshold_db: float = -40.0, min_duration: float = 0.5,
                    start_time: float = None, end_time: float = None) -> List[Dict]:
    """Detect silent regions in the audio."""
    params = {
        "threshold_db": threshold_db,
        "min_duration": min_duration
    }
    if start_time is not None:
        params["start_time"] = start_time
    if end_time is not None:
        params["end_time"] = end_time

    result = self.executor.execute_state_query("detect_silences", params)
    if result.get("success"):
        return result.get("regions", [])
    return []

# In ToolRegistry._build_tool_map():
"detect_silences": self._detect_silences_wrapper,

# Wrapper method:
def _detect_silences_wrapper(self, threshold_db: float = -40.0,
                              min_duration: float = 0.5,
                              start_time: float = None,
                              end_time: float = None) -> Dict[str, Any]:
    regions = self.state.detect_silences(threshold_db, min_duration, start_time, end_time)
    return {"success": True, "regions": regions, "count": len(regions)}
```

### Success Criteria

#### Automated Verification:
- [ ] Build succeeds with new IAgentStateReader methods
- [ ] Python tests pass: `python -m pytest src/chat/python/tests/`
- [ ] State query `detect_silences` returns valid JSON

#### Manual Verification:
- [ ] Load a podcast with pauses, ask "find silences longer than 1 second"
- [ ] Results show in chat with correct timestamps
- [ ] Timestamps match actual silence positions in audio

---

## Phase 2: Timeline Overlay Visualization

### Overview
Add a system to show temporary visual overlays on the timeline for analysis results (silence regions, loudness issues, transcript matches).

### Changes Required

#### 2.1 Create Analysis Overlay Model

**File**: `src/projectscene/view/timeline/analysisoverlaymodel.h` (new)
**Changes**: Create model for managing overlay data

```cpp
#pragma once

#include <QObject>
#include <QAbstractListModel>
#include <vector>

namespace au::projectscene {

struct AnalysisRegion {
    QString id;
    double startTime;
    double endTime;
    QString label;
    QString category;  // "silence", "loudness", "transcript"
    QColor color;
    bool selected = false;
};

class AnalysisOverlayModel : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(bool visible READ visible WRITE setVisible NOTIFY visibleChanged)
    Q_PROPERTY(int count READ count NOTIFY regionsChanged)

public:
    enum Roles {
        IdRole = Qt::UserRole + 1,
        StartTimeRole,
        EndTimeRole,
        LabelRole,
        CategoryRole,
        ColorRole,
        SelectedRole
    };

    explicit AnalysisOverlayModel(QObject* parent = nullptr);

    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    bool visible() const;
    void setVisible(bool visible);
    int count() const;

    Q_INVOKABLE void setRegions(const QVariantList& regions);
    Q_INVOKABLE void clearRegions();
    Q_INVOKABLE void selectRegion(const QString& id);
    Q_INVOKABLE void navigateToRegion(const QString& id);

signals:
    void visibleChanged();
    void regionsChanged();
    void navigateRequested(double time);

private:
    std::vector<AnalysisRegion> m_regions;
    bool m_visible = false;
};

} // namespace au::projectscene
```

#### 2.2 Create QML Overlay Component

**File**: `src/projectscene/qml/Audacity/ProjectScene/AnalysisOverlay.qml` (new)
**Changes**: Visual component for rendering overlays on timeline

```qml
import QtQuick 2.15

Item {
    id: root

    property var model: null
    property real pixelsPerSecond: 100
    property real viewportStart: 0

    visible: model ? model.visible : false

    Repeater {
        model: root.model

        Rectangle {
            x: (model.startTime - root.viewportStart) * root.pixelsPerSecond
            width: (model.endTime - model.startTime) * root.pixelsPerSecond
            height: parent.height
            color: model.color
            opacity: model.selected ? 0.5 : 0.3

            border.width: model.selected ? 2 : 1
            border.color: Qt.darker(model.color, 1.3)

            Text {
                anchors.centerIn: parent
                text: model.label
                color: "white"
                font.pixelSize: 10
                visible: parent.width > 40
            }

            MouseArea {
                anchors.fill: parent
                onClicked: root.model.selectRegion(model.id)
                onDoubleClicked: root.model.navigateToRegion(model.id)
            }
        }
    }
}
```

#### 2.3 Integrate with Track View

**File**: `src/projectscene/qml/Audacity/ProjectScene/TrackItemsView.qml`
**Changes**: Add overlay layer on top of tracks

```qml
// Add import and property
property var analysisOverlayModel: null

// Add overlay component after track items
AnalysisOverlay {
    anchors.fill: parent
    model: analysisOverlayModel
    pixelsPerSecond: root.pixelsPerSecond
    viewportStart: root.viewportStart
    z: 100  // Above track content
}
```

#### 2.4 Connect to Chat Results

**File**: `src/chat/view/chatviewmodel.cpp`
**Changes**: When analysis results arrive, populate overlay model

```cpp
void ChatViewModel::handleAnalysisResults(const QVariantMap& results) {
    if (results.contains("regions")) {
        QVariantList overlayRegions;
        const auto regions = results["regions"].toList();

        for (int i = 0; i < regions.size(); ++i) {
            const auto& r = regions[i].toMap();
            QVariantMap overlay;
            overlay["id"] = QString("region_%1").arg(i);
            overlay["startTime"] = r["start_time"];
            overlay["endTime"] = r["end_time"];
            overlay["label"] = formatDuration(r["duration"].toDouble());
            overlay["category"] = results.value("category", "silence").toString();
            overlay["color"] = categoryColor(overlay["category"].toString());
            overlayRegions.append(overlay);
        }

        emit analysisOverlayRequested(overlayRegions);
    }
}
```

### Success Criteria

#### Automated Verification:
- [ ] Build succeeds with new QML components
- [ ] AnalysisOverlayModel unit tests pass

#### Manual Verification:
- [ ] Detect silences → colored regions appear on timeline
- [ ] Clicking region selects it (visual feedback)
- [ ] Double-clicking navigates playhead to that position
- [ ] Overlays disappear when cleared or new analysis runs

---

## Phase 3: Loudness Analysis

### Overview
Expose per-track LUFS measurement and provide suggestions for normalization.

### Changes Required

#### 3.1 Add Loudness Analysis to IAgentStateReader

**File**: `src/chat/iagentstatereader.h`
**Changes**: Add loudness analysis method

```cpp
struct TrackLoudness {
    QString trackId;
    QString trackName;
    double lufs;           // Integrated loudness
    double peakDb;         // True peak
    double dynamicRange;   // Loudness range
};

virtual std::vector<TrackLoudness> analyzeLoudness(
    std::optional<double> startTime = std::nullopt,
    std::optional<double> endTime = std::nullopt
) const = 0;
```

#### 3.2 Implement Using EBUR128

**File**: `src/chat/internal/agentstatereader.cpp`
**Changes**: Implement loudness analysis per track

```cpp
std::vector<TrackLoudness> AgentStateReader::analyzeLoudness(
    std::optional<double> startTime,
    std::optional<double> endTime
) const
{
    std::vector<TrackLoudness> results;

    auto project = globalContext()->currentProject();
    if (!project) return results;

    auto& trackList = TrackList::Get(project->au3Project());
    double t0 = startTime.value_or(0.0);
    double t1 = endTime.value_or(project->totalTime());

    for (auto track : trackList.Any<WaveTrack>()) {
        size_t nChannels = track->NChannels();
        double rate = track->GetRate();

        EBUR128 loudnessProcessor(rate, nChannels);

        // Process all samples in range
        auto start = track->TimeToLongSamples(t0);
        auto end = track->TimeToLongSamples(t1);

        Floats buffer(track->GetMaxBlockSize());
        for (auto s = start; s < end; ) {
            auto blockLen = std::min(track->GetBestBlockSize(s), (end - s).as_size_t());

            for (size_t ch = 0; ch < nChannels; ++ch) {
                track->GetChannel(ch)->GetFloats(buffer.get(), s, blockLen);
                for (size_t i = 0; i < blockLen; ++i) {
                    loudnessProcessor.ProcessSampleFromChannel(buffer[i], ch);
                }
            }
            for (size_t i = 0; i < blockLen; ++i) {
                loudnessProcessor.NextSample();
            }
            s += blockLen;
        }

        double loudness = loudnessProcessor.IntegrativeLoudness();
        double lufs = 10.0 * log10(loudness);  // Convert to LUFS

        results.push_back({
            QString::fromStdString(track->GetId().IsOk() ? track->GetId().ToString() : ""),
            QString::fromStdWString(track->GetName()),
            lufs,
            0.0,  // TODO: calculate true peak
            0.0   // TODO: calculate loudness range
        });
    }

    return results;
}
```

#### 3.3 Add Python Tool

**File**: `src/chat/python/tool_schemas.py`
**Changes**: Add analyze_loudness tool

```python
{
    "type": "function",
    "function": {
        "name": "analyze_loudness",
        "description": "Analyze the loudness (LUFS) of each track. Returns integrated loudness per track. Use this to check if tracks are balanced or need normalization. Podcast standard is -16 LUFS (stereo) or -19 LUFS (mono).",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "number",
                    "description": "Start of region to analyze (seconds). Omit for full track."
                },
                "end_time": {
                    "type": "number",
                    "description": "End of region to analyze (seconds). Omit for full track."
                }
            },
            "required": []
        }
    }
}
```

#### 3.4 Enhance Orchestrator for Loudness Suggestions

**File**: `src/chat/python/orchestrator.py`
**Changes**: Add logic to interpret loudness results and suggest actions

```python
def _format_loudness_results(self, results: List[Dict]) -> str:
    """Format loudness analysis with recommendations."""
    lines = ["**Track Loudness Analysis:**\n"]

    target_lufs = -16.0  # Podcast standard for stereo

    for track in results:
        lufs = track["lufs"]
        name = track["track_name"] or f"Track {track['track_id'][:8]}"
        diff = lufs - target_lufs

        status = ""
        if abs(diff) < 1.0:
            status = "✓ Good"
        elif diff > 0:
            status = f"⚠️ {abs(diff):.1f} dB too loud"
        else:
            status = f"⚠️ {abs(diff):.1f} dB too quiet"

        lines.append(f"- **{name}**: {lufs:.1f} LUFS {status}")

    if any(abs(t["lufs"] - target_lufs) > 1.0 for t in results):
        lines.append("\n*Would you like me to normalize these to -16 LUFS?*")

    return "\n".join(lines)
```

### Success Criteria

#### Automated Verification:
- [ ] Build succeeds with EBUR128 integration
- [ ] Loudness values are within 0.5 LUFS of reference tools

#### Manual Verification:
- [ ] "Check the levels" shows LUFS for each track
- [ ] Tracks with different levels show appropriate warnings
- [ ] "Normalize to -16 LUFS" applies correct gain to each track

---

## Phase 4: Transcription Integration

### Overview
Integrate CrisperWhisper API for verbatim transcription with filler word detection.

### Changes Required

#### 4.1 Create Transcription Service

**File**: `src/chat/python/transcription_service.py` (new)
**Changes**: Service to handle audio export and API calls

```python
#!/usr/bin/env python3
"""
Transcription service using CrisperWhisper API.
Provides verbatim transcription with filler words preserved.
"""

import os
import tempfile
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import requests

from config import get_config_value


@dataclass
class TranscriptWord:
    word: str
    start_time: float
    end_time: float
    confidence: float
    is_filler: bool = False


@dataclass
class TranscriptSegment:
    text: str
    start_time: float
    end_time: float
    words: List[TranscriptWord]


class TranscriptionService:
    """Service for transcribing audio using CrisperWhisper API."""

    FILLER_WORDS = {"uh", "um", "uhm", "ah", "er", "like", "you know", "actually", "basically", "literally"}

    def __init__(self):
        self.api_endpoint = get_config_value("CRISPERWHISPER_API_ENDPOINT",
                                              "https://api.crisperwhisper.com/v1/transcribe")
        self.api_key = get_config_value("CRISPERWHISPER_API_KEY", "")

    def transcribe_file(self, audio_path: str, language: str = "en") -> Dict[str, Any]:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            language: Language code (default: "en")

        Returns:
            Dict with segments, words, and full text
        """
        if not self.api_key:
            return {"error": "CRISPERWHISPER_API_KEY not configured"}

        with open(audio_path, "rb") as f:
            response = requests.post(
                self.api_endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"audio": f},
                data={
                    "language": language,
                    "word_timestamps": True,
                    "verbatim": True  # Keep filler words
                }
            )

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code} - {response.text}"}

        result = response.json()
        return self._process_response(result)

    def _process_response(self, api_result: Dict) -> Dict[str, Any]:
        """Process API response and mark filler words."""
        segments = []
        all_words = []

        for seg in api_result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                word_text = w["word"].strip().lower()
                is_filler = word_text in self.FILLER_WORDS

                word = TranscriptWord(
                    word=w["word"],
                    start_time=w["start"],
                    end_time=w["end"],
                    confidence=w.get("confidence", 1.0),
                    is_filler=is_filler
                )
                words.append(word)
                all_words.append(word)

            segments.append(TranscriptSegment(
                text=seg["text"],
                start_time=seg["start"],
                end_time=seg["end"],
                words=words
            ))

        return {
            "success": True,
            "segments": [self._segment_to_dict(s) for s in segments],
            "words": [self._word_to_dict(w) for w in all_words],
            "full_text": " ".join(s.text for s in segments),
            "filler_count": sum(1 for w in all_words if w.is_filler),
            "filler_words": [self._word_to_dict(w) for w in all_words if w.is_filler]
        }

    def _word_to_dict(self, word: TranscriptWord) -> Dict:
        return {
            "word": word.word,
            "start_time": word.start_time,
            "end_time": word.end_time,
            "confidence": word.confidence,
            "is_filler": word.is_filler
        }

    def _segment_to_dict(self, segment: TranscriptSegment) -> Dict:
        return {
            "text": segment.text,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "words": [self._word_to_dict(w) for w in segment.words]
        }

    def search_transcript(self, transcript: Dict, query: str) -> List[Dict]:
        """
        Search transcript for a phrase or word.

        Args:
            transcript: Result from transcribe_file()
            query: Text to search for

        Returns:
            List of matches with time ranges
        """
        matches = []
        query_lower = query.lower()

        # Search in segment text for phrase matches
        for seg in transcript.get("segments", []):
            if query_lower in seg["text"].lower():
                matches.append({
                    "text": seg["text"],
                    "start_time": seg["start_time"],
                    "end_time": seg["end_time"],
                    "match_type": "phrase"
                })

        # Search individual words
        for word in transcript.get("words", []):
            if query_lower in word["word"].lower():
                matches.append({
                    "text": word["word"],
                    "start_time": word["start_time"],
                    "end_time": word["end_time"],
                    "match_type": "word"
                })

        return matches
```

#### 4.2 Add Audio Export for Transcription

**File**: `src/chat/internal/agentstatereader.cpp`
**Changes**: Add method to export audio region to temp file

```cpp
QString AgentStateReader::exportAudioRegion(
    double startTime,
    double endTime,
    const QString& format  // "wav", "mp3"
) const
{
    // Create temp file
    QString tempPath = QDir::tempPath() + "/audacity_transcribe_" +
                       QUuid::createUuid().toString(QUuid::Id128) + "." + format;

    // Use existing export infrastructure to write audio
    // ... implementation using Au3Exporter ...

    return tempPath;
}
```

#### 4.3 Add Transcription Tools

**File**: `src/chat/python/tool_schemas.py`
**Changes**: Add transcribe and search tools

```python
{
    "type": "function",
    "function": {
        "name": "transcribe_audio",
        "description": "Transcribe the audio to text with word-level timestamps. Preserves filler words (um, uh, like, etc.) for identification. Returns full transcript and marks filler words.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "number",
                    "description": "Start of region to transcribe (seconds). Omit for full project."
                },
                "end_time": {
                    "type": "number",
                    "description": "End of region to transcribe (seconds). Omit for full project."
                },
                "language": {
                    "type": "string",
                    "description": "Language code (default: 'en')"
                }
            },
            "required": []
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "search_transcript",
        "description": "Search the transcript for a word or phrase. Returns all occurrences with timestamps. Must call transcribe_audio first.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Word or phrase to search for"
                }
            },
            "required": ["query"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "find_filler_words",
        "description": "Find all filler words (um, uh, like, you know, etc.) in the transcript. Must call transcribe_audio first.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
```

#### 4.4 Orchestrator Transcript Caching

**File**: `src/chat/python/orchestrator.py`
**Changes**: Cache transcript for search operations

```python
class OrchestratorAgent:
    def __init__(self, tools):
        # ... existing init ...
        self.cached_transcript = None
        self.transcription_service = TranscriptionService()

    def _handle_transcription(self, start_time=None, end_time=None, language="en"):
        """Handle transcribe_audio tool call."""
        # Export audio region
        export_result = self.tools.state.export_audio_region(start_time, end_time)
        if not export_result.get("success"):
            return {"error": "Failed to export audio"}

        audio_path = export_result["path"]

        try:
            # Transcribe
            transcript = self.transcription_service.transcribe_file(audio_path, language)

            # Cache for subsequent searches
            self.cached_transcript = transcript

            return transcript
        finally:
            # Clean up temp file
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _handle_search_transcript(self, query: str):
        """Handle search_transcript tool call."""
        if not self.cached_transcript:
            return {"error": "No transcript available. Call transcribe_audio first."}

        matches = self.transcription_service.search_transcript(self.cached_transcript, query)
        return {"success": True, "matches": matches, "count": len(matches)}

    def _handle_find_filler_words(self):
        """Handle find_filler_words tool call."""
        if not self.cached_transcript:
            return {"error": "No transcript available. Call transcribe_audio first."}

        filler_words = self.cached_transcript.get("filler_words", [])
        return {
            "success": True,
            "filler_words": filler_words,
            "count": len(filler_words),
            "summary": self._summarize_fillers(filler_words)
        }

    def _summarize_fillers(self, fillers: List[Dict]) -> str:
        """Summarize filler word occurrences."""
        counts = {}
        for f in fillers:
            word = f["word"].lower().strip()
            counts[word] = counts.get(word, 0) + 1

        summary = ", ".join(f"{word}: {count}" for word, count in sorted(counts.items(), key=lambda x: -x[1]))
        return summary
```

### Success Criteria

#### Automated Verification:
- [ ] TranscriptionService unit tests pass with mock API
- [ ] Filler word detection correctly identifies known fillers
- [ ] Search returns correct time ranges

#### Manual Verification:
- [ ] "Transcribe the audio" calls API and returns text with timestamps
- [ ] "Find where I said 'actually'" returns correct locations
- [ ] "Find filler words" shows all um/uh with counts
- [ ] Clicking result in chat navigates to that time in timeline
- [ ] Timeline overlay highlights filler word positions

---

## Phase 5: Approval Workflow for Bulk Operations

### Overview
Enhance the approval workflow to handle bulk operations with selective approval.

### Changes Required

#### 5.1 Bulk Approval Panel

**File**: `src/chat/qml/Audacity/Chat/BulkApprovalPanel.qml` (new)
**Changes**: UI for approving/rejecting individual items in a batch

```qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property var items: []  // List of {id, label, startTime, endTime, selected}
    property string actionDescription: "Remove selected"

    signal approved(var selectedIds)
    signal cancelled()
    signal itemToggled(string id, bool selected)
    signal navigateToItem(string id)

    color: "#2d2d2d"
    radius: 8

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        Text {
            text: "Found " + items.length + " items"
            color: "#ffffff"
            font.bold: true
        }

        // Select All / None
        RowLayout {
            spacing: 8
            Button {
                text: "Select All"
                onClicked: items.forEach(i => root.itemToggled(i.id, true))
            }
            Button {
                text: "Select None"
                onClicked: items.forEach(i => root.itemToggled(i.id, false))
            }
        }

        // Scrollable list of items
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                model: root.items
                delegate: ItemDelegate {
                    width: parent.width
                    height: 40

                    RowLayout {
                        anchors.fill: parent
                        spacing: 8

                        CheckBox {
                            checked: modelData.selected
                            onToggled: root.itemToggled(modelData.id, checked)
                        }

                        Text {
                            text: modelData.label
                            color: "#ffffff"
                            Layout.fillWidth: true
                        }

                        Text {
                            text: formatTime(modelData.startTime) + " - " + formatTime(modelData.endTime)
                            color: "#aaaaaa"
                            font.pixelSize: 11
                        }

                        Button {
                            text: "▶"
                            onClicked: root.navigateToItem(modelData.id)
                        }
                    }
                }
            }
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Button {
                text: "Cancel"
                onClicked: root.cancelled()
            }

            Item { Layout.fillWidth: true }

            Button {
                text: root.actionDescription + " (" + selectedCount + ")"
                enabled: selectedCount > 0
                highlighted: true
                onClicked: {
                    var selected = items.filter(i => i.selected).map(i => i.id)
                    root.approved(selected)
                }

                property int selectedCount: items.filter(i => i.selected).length
            }
        }
    }

    function formatTime(seconds) {
        var mins = Math.floor(seconds / 60)
        var secs = Math.floor(seconds % 60)
        return mins + ":" + secs.toString().padStart(2, "0")
    }
}
```

#### 5.2 Bulk Deletion Implementation

**File**: `src/chat/python/orchestrator.py`
**Changes**: Handle bulk delete approval

```python
def process_bulk_approval(self, approval_id: str, selected_ids: List[str],
                          regions: List[Dict]) -> Dict[str, Any]:
    """
    Process bulk approval for region deletions.

    Args:
        approval_id: ID of the approval request
        selected_ids: List of region IDs user approved
        regions: Full list of detected regions

    Returns:
        Result of the bulk operation
    """
    # Filter to only selected regions
    selected_regions = [r for r in regions if r["id"] in selected_ids]

    if not selected_regions:
        return {"type": "message", "content": "No regions selected.", "can_undo": False}

    # Sort by start time descending (delete from end to preserve earlier timestamps)
    selected_regions.sort(key=lambda r: r["start_time"], reverse=True)

    deleted_count = 0
    errors = []

    for region in selected_regions:
        # Select the region
        result = self.tools.selection.set_time_selection(
            region["start_time"],
            region["end_time"]
        )
        if not result.get("success"):
            errors.append(f"Failed to select {region['id']}")
            continue

        # Delete it
        result = self.tools.editing.delete()
        if result.get("success"):
            deleted_count += 1
        else:
            errors.append(f"Failed to delete {region['id']}")

    if errors:
        return {
            "type": "message",
            "content": f"Deleted {deleted_count} regions. Errors: {'; '.join(errors)}",
            "can_undo": deleted_count > 0
        }
    else:
        return {
            "type": "message",
            "content": f"Deleted {deleted_count} silence regions.",
            "can_undo": True
        }
```

### Success Criteria

#### Automated Verification:
- [ ] BulkApprovalPanel renders correctly
- [ ] Select all/none toggles work
- [ ] Approved list contains only selected IDs

#### Manual Verification:
- [ ] Detect silences → shows list with checkboxes
- [ ] Can select/deselect individual items
- [ ] Clicking play button navigates to that region
- [ ] "Remove selected" only deletes checked items
- [ ] Undo restores all deleted regions

---

## Testing Strategy

### Unit Tests

**Python tests** (`src/chat/python/tests/`):
- `test_transcription_service.py` - Mock API responses, filler detection
- `test_silence_detection_tool.py` - State query integration
- `test_loudness_analysis_tool.py` - LUFS calculation validation
- `test_bulk_approval.py` - Approval workflow logic

**C++ tests**:
- `AgentStateReader` silence detection with known audio
- `AgentStateReader` loudness analysis vs reference values

### Integration Tests

- End-to-end: "Find silences" → approval → deletion
- End-to-end: "Transcribe" → "Find ums" → delete selected
- End-to-end: "Check levels" → "Normalize to -16" → verify LUFS

### Manual Testing Steps

1. Load a podcast recording with pauses and filler words
2. "Find all silences longer than 2 seconds" → verify visual overlay
3. Select some, delete, verify audio
4. Undo, verify restored
5. "Transcribe the audio" → verify text appears
6. "Find where I said um" → verify locations correct
7. "Check the levels" → verify LUFS values reasonable
8. "Normalize to -16 LUFS" → verify post-normalization levels

---

## Performance Considerations

### Silence Detection
- Uses block-based processing (already optimized in TruncSilenceBase)
- For long podcasts (1+ hours), consider progress reporting

### Loudness Analysis
- EBUR128 processes all samples - O(n) where n = sample count
- For 1 hour @ 44.1kHz stereo: ~320M samples
- Consider chunked analysis with progress for files > 30 min

### Transcription
- Depends on API latency
- Consider chunking for files > 10 min (API limits)
- Cache transcript in session to avoid re-transcription

### Timeline Overlay
- Rendering many regions (100+) could impact UI performance
- Consider virtualization if > 50 regions

---

## Migration Notes

- New tools are additive - no breaking changes to existing functionality
- Transcription requires API key configuration (new config option)
- Timeline overlay system can be extended for other analysis visualizations

---

## References

- Research document: `thoughts/shared/research/2025-12-07-audio-editing-mapping.md`
- Silence detection: `au3/libraries/lib-builtin-effects/TruncSilenceBase.h:58`
- LUFS measurement: `au3/libraries/lib-math/EBUR128.cpp:115`
- Current chat tools: `src/chat/python/tools.py`
- CrisperWhisper paper: https://arxiv.org/html/2408.16589v1
