# Podcast AI Chat Assistant Expansion Plan

## Overview

Expand the existing Audacity AI chat assistant to support podcast-focused workflows. This plan focuses on **enhancing chat intelligence** (OpenAI integration, transcription) while working within **existing backend tool availability**. Tests that cannot be executed due to missing backend tools are explicitly noted.

## Current State Analysis

### What Exists
- C++/Python bridge architecture with JSON-RPC over stdin/stdout
- QML chat UI with approval workflow (batch and step-by-step modes)
- Keyword-based intent parsing (6 intents: SELECT, APPLY_EFFECT, EDIT, CREATE_TRACK, DELETE, PLAYBACK)
- Tool registry with ~48 action codes
- OpenAI SDK imported but not activated
- Label track infrastructure (can store timestamped transcription)

### Key Gaps
1. **No transcription** - Required for content-aware features (Levels 2+)
2. **Keyword-only parsing** - OpenAI client exists but unused
3. **No time-based selection** - `set_time_selection(start, end)` tool missing
4. **Effects open dialogs** - No auto-apply with parameters
5. **No contextual memory** - Each request is stateless
6. **No audio analysis** - Can't detect silence, filler words, volume levels

## Desired End State

A chat assistant that can:
1. Understand natural language podcast editing requests via OpenAI
2. Transcribe audio content via Whisper API
3. Execute available Audacity actions intelligently
4. Gracefully handle unavailable operations with helpful feedback
5. Maintain conversation context for multi-turn interactions

## What We Prefer to Avoid

- Adding new C++ backend tools/actions (prefer using existing, but will add if high-value)
- Building custom ML models (use OpenAI/Whisper APIs)
- Modifying the approval workflow UI
- Adding real-time preview capabilities
- Building a plugin system

---

## Test Matrix with Tool Availability

### Legend
- **TOOL_AVAILABLE**: Backend tool exists, test can be implemented
- **TOOL_MISSING**: Backend tool does not exist, test blocked
- **PARTIAL**: Some functionality available, limited test possible

---

## Level 1: Simple Commands (MVP-Critical)

### Test 1.1: Basic Edits & Navigation

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Cut everything before the intro" | **TOOL_MISSING** | Requires `set_time_selection(start, end)` - only `select-all`, `select-track-start-to-cursor` exist |
| "Trim the last 30 seconds" | **TOOL_MISSING** | Requires time-based selection |
| "Split this at 12:05" | **PARTIAL** | `split` exists but positions at cursor, not arbitrary time |
| "Delete from 3:10 to 4:02" | **TOOL_MISSING** | Requires time-based selection |

**Implementation**: Enhance intent parsing to recognize these patterns. Return helpful message when tool unavailable.

### Test 1.2: Basic Voice Cleanup

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Reduce the background hiss" | **TOOL_AVAILABLE** | `action://effects/open?effectId=noisereduction` - opens dialog |
| "Make this less noisy" | **TOOL_AVAILABLE** | Same as above |
| "Fix the pop at 2:45" | **TOOL_MISSING** | Requires time selection + click removal effect |
| "Lower the echo" | **TOOL_MISSING** | No de-reverb/echo reduction effect registered |

**Implementation**: Map natural language to effect IDs. Note that effects open dialogs (no auto-apply).

### Test 1.3: Basic Leveling

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Balance the volume" | **TOOL_AVAILABLE** | `normalize` effect available |
| "Normalize loudness" | **TOOL_AVAILABLE** | `normalize` or loudness normalization effect |

**Implementation**: These work via effect dialog. LUFS targeting requires user to set in dialog.

### Test 1.4: Simple Undo/Preview

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Undo the last change" | **TOOL_AVAILABLE** | `action://trackedit/undo` |
| "Preview before applying" | **TOOL_MISSING** | No preview action exists |

---

## Level 2: Intermediate Commands

### Test 2.5: Filler Word Removal

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Remove ums and uhs" | **TOOL_MISSING** | Requires: transcription + time selection + delete. Time selection blocked. |
| "Reduce filler words but keep it natural" | **TOOL_MISSING** | Same as above |

**Implementation**: With transcription, can DETECT filler words and report timestamps. Cannot auto-remove without time selection tool.

### Test 2.6: Basic Content Analysis

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Give me timestamps for topic changes" | **PARTIAL** | Transcription can detect, but no label track write action |
| "Where does the interview start?" | **PARTIAL** | Transcription + LLM analysis can answer, returns text only |

**Implementation**: Transcription + OpenAI analysis. Output is chat message (no label creation).

### Test 2.7: Contextual Requests

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Do the same thing for the next section" | **TOOL_MISSING** | Requires: memory + time selection |
| "Make this less aggressive" | **TOOL_MISSING** | Ambiguous, no specific tool mapping |

**Implementation**: Add conversation memory to orchestrator. Execution blocked by time selection.

### Test 2.8: Summaries & Notes

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Summarize this episode" | **TOOL_AVAILABLE** | Transcription + OpenAI summarization (output is text) |
| "Write show notes" | **TOOL_AVAILABLE** | Same - text generation only |

**Implementation**: Full implementation possible. Output is chat message.

---

## Level 3: Complex Commands

### Test 3.9: Auto Tighten/Shorten

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Make this 15% shorter" | **TOOL_MISSING** | Requires silence detection + time selection + delete |
| "Tighten up the slow parts" | **TOOL_MISSING** | Same |

**Implementation**: Can analyze and report slow parts. Cannot execute edits.

### Test 3.10: Detect & Fix Issues

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Find places where I stumble" | **PARTIAL** | Transcription can detect, returns timestamps |
| "Cut the awkward segments" | **TOOL_MISSING** | Detection possible, edit blocked |

### Test 3.11: Topic-Level Segmentation

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Break this into chapters" | **PARTIAL** | Can generate chapter list, no label track write |
| "Label each segment" | **TOOL_MISSING** | No label creation action |

### Test 3.12: Multi-Action Commands

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Remove filler, clean noise, and balance voices" | **PARTIAL** | Can execute noise + normalize in sequence. Filler removal blocked. |
| "Cut the intro and level the rest" | **TOOL_MISSING** | Time selection blocked |

---

## Level 4: Advanced Commands

### Test 4.13: Intent-Based Cleanup

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Make this sound professional" | **PARTIAL** | Can apply: normalize, noise reduction, compressor (via dialogs) |
| "Fix the messy parts" | **TOOL_MISSING** | Requires detection + time selection |
| "Do your magic" | **PARTIAL** | Best-effort with available effects |

### Test 4.14: Diagnostics & Suggestions

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Where are the issues?" | **TOOL_AVAILABLE** | Transcription + analysis = text report |
| "How can I improve pacing?" | **TOOL_AVAILABLE** | Analysis only, no execution |
| "Any places to cut?" | **TOOL_AVAILABLE** | Analysis only |

### Test 4.15: Quantified Performance

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "How many filler words removed?" | **TOOL_MISSING** | Can count detected, cannot remove |
| "How much did you shorten it?" | **TOOL_MISSING** | Cannot shorten |
| "How much time did we save?" | **TOOL_MISSING** | Cannot execute time-saving edits |

### Test 4.16: Style & Tone Editing

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Make it more conversational" | **TOOL_MISSING** | Ambiguous, no mapping |
| "Keep laughter but not coughing" | **TOOL_MISSING** | Requires audio classification + time selection |
| "Remove dramatic pauses" | **TOOL_MISSING** | Silence detection + time selection |

---

## Level 5: Specialized Content Generation

### Test 5.17: Publish-Ready Materials

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Write an episode description" | **TOOL_AVAILABLE** | Transcription + OpenAI |
| "Generate social posts" | **TOOL_AVAILABLE** | Text generation |
| "Write a teaser" | **TOOL_AVAILABLE** | Text generation |

### Test 5.18: Multi-Platform Outputs

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Create three captions for LinkedIn" | **TOOL_AVAILABLE** | Text generation |
| "Write an email announcement" | **TOOL_AVAILABLE** | Text generation |

---

## Level 6: Meta & Collaborative

### Test 6.19: Workflow Feedback

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "How does this sound now?" | **TOOL_MISSING** | No audio analysis feedback loop |
| "Rate clarity, pacing, and loudness" | **PARTIAL** | Can analyze transcription for pacing, not loudness |

### Test 6.20: Collaborative Editorial Review

| Test Case | Tool Status | Notes |
|-----------|-------------|-------|
| "Flag issues in the first 10 minutes" | **PARTIAL** | Can analyze, cannot create markers |
| "Add comments to timestamps" | **TOOL_MISSING** | No label/comment creation |

---

## Implementation Phases

### Phase 1: OpenAI Integration & Enhanced Parsing

**Goal**: Replace keyword matching with LLM-based intent parsing

**Changes Required**:

#### 1.1 Update orchestrator.py

**File**: `src/chat/python/orchestrator.py`

Add LLM-based intent parsing using the existing OpenAI client:

```python
# New method in OrchestratorAgent class
def _parse_intent_with_llm(self, message: str) -> tuple[Intent, Dict[str, Any]]:
    """
    Use OpenAI to parse user intent and extract parameters
    """
    if not self.openai_client:
        return self._parse_intent(message), {}

    response = self.openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": INTENT_PARSING_PROMPT},
            {"role": "user", "content": message}
        ],
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    intent = Intent(result.get("intent", "unknown"))
    parameters = result.get("parameters", {})

    return intent, parameters
```

Add system prompt for intent parsing:

```python
INTENT_PARSING_PROMPT = """You are an audio editing assistant for Audacity. Parse the user's request and return JSON with:

{
  "intent": "select|apply_effect|edit|create_track|delete|playback|analyze|generate_text|unknown",
  "parameters": {
    "effect_name": "string if applying effect",
    "start_time": "float in seconds if time specified",
    "end_time": "float in seconds if time specified",
    "edit_type": "cut|copy|paste|delete|split|join",
    "analysis_type": "transcribe|summarize|find_issues|detect_filler",
    "generation_type": "show_notes|description|social_post"
  },
  "requires_transcription": true/false,
  "tool_available": true/false,
  "unavailable_reason": "string if tool_available is false"
}

Available tools:
- Effects: noise reduction, normalize, amplify, fade in/out, compressor, limiter, reverb (open dialogs)
- Editing: cut, copy, paste, delete, split, join, undo, redo (on current selection)
- Selection: select all, clear selection (NO time-based selection available)
- Playback: play, stop, pause
- Track: create mono/stereo track, delete track

NOT available:
- Time-based selection (cannot select "from 1:00 to 2:00")
- Automatic effect application (effects open dialogs)
- Label/marker creation
- Audio analysis (loudness, silence detection)
"""
```

#### 1.2 Add conversation memory

**File**: `src/chat/python/orchestrator.py`

```python
class OrchestratorAgent:
    def __init__(self, ...):
        # ... existing init
        self.conversation_history: List[Dict[str, str]] = []
        self.last_action: Optional[Dict[str, Any]] = None

    def process_request(self, user_message: str) -> Dict[str, Any]:
        # Add to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # ... existing processing

        # Store last action for "do it again" requests
        if result.get("type") == "message":
            self.conversation_history.append({"role": "assistant", "content": result["content"]})

        return result
```

#### 1.3 Update config.py for Whisper

**File**: `src/chat/python/config.py`

```python
def get_whisper_model() -> str:
    """Get Whisper model to use"""
    return os.getenv("WHISPER_MODEL", "whisper-1")

def is_transcription_enabled() -> bool:
    """Check if transcription is enabled (requires OpenAI key)"""
    return is_openai_configured()
```

**Success Criteria**:

#### Automated Verification:
- [x] Python syntax valid: `python3 -m py_compile src/chat/python/orchestrator.py`
- [x] Config imports work: `python3 -c "from config import is_transcription_enabled"`
- [ ] OpenAI client initializes when key present

#### Manual Verification:
- [ ] Chat understands "apply noise reduction" via LLM
- [ ] Chat understands "clean up the audio" as noise reduction intent
- [ ] Chat remembers previous request in conversation
- [ ] Chat understands "select from 2s to 3s" and executes time selection

---

### Phase 2: Transcription Service

**Goal**: Add Whisper-based transcription for content analysis

**Changes Required**:

#### 2.1 Create transcription_agent.py

**File**: `src/chat/python/transcription_agent.py`

```python
#!/usr/bin/env python3
"""
Transcription Agent
Handles audio transcription via OpenAI Whisper API
"""

import os
import tempfile
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from config import get_openai_api_key, get_whisper_model, is_transcription_enabled

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio"""
    start: float  # seconds
    end: float    # seconds
    text: str


@dataclass
class Transcript:
    """Full transcript with segments"""
    full_text: str
    segments: List[TranscriptSegment]
    duration: float
    language: str


class TranscriptionAgent:
    """
    Agent for transcribing audio using Whisper API
    """

    def __init__(self):
        self.client = None
        self.cached_transcript: Optional[Transcript] = None
        self.cached_audio_path: Optional[str] = None

        if OPENAI_AVAILABLE and is_transcription_enabled():
            self.client = OpenAI(api_key=get_openai_api_key())

    def is_available(self) -> bool:
        """Check if transcription is available"""
        return self.client is not None

    def transcribe_file(self, audio_path: str, force: bool = False) -> Dict[str, Any]:
        """
        Transcribe an audio file

        Args:
            audio_path: Path to audio file
            force: Force re-transcription even if cached

        Returns:
            Dict with transcript data or error
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Transcription not available. Set OPENAI_API_KEY."
            }

        # Check cache
        if not force and self.cached_audio_path == audio_path and self.cached_transcript:
            return {
                "success": True,
                "transcript": self.cached_transcript,
                "cached": True
            }

        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=get_whisper_model(),
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            segments = [
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text
                )
                for seg in response.segments
            ]

            transcript = Transcript(
                full_text=response.text,
                segments=segments,
                duration=response.duration,
                language=response.language
            )

            # Cache result
            self.cached_transcript = transcript
            self.cached_audio_path = audio_path

            return {
                "success": True,
                "transcript": transcript,
                "cached": False
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Transcription failed: {str(e)}"
            }

    def find_filler_words(self, transcript: Transcript) -> List[Dict[str, Any]]:
        """
        Find filler words in transcript

        Returns list of {start, end, word, segment_index}
        """
        filler_patterns = [
            "um", "uh", "er", "ah", "like", "you know",
            "basically", "actually", "literally", "so", "well"
        ]

        fillers = []
        for i, segment in enumerate(transcript.segments):
            text_lower = segment.text.lower()
            for filler in filler_patterns:
                if filler in text_lower:
                    fillers.append({
                        "start": segment.start,
                        "end": segment.end,
                        "word": filler,
                        "segment_index": i,
                        "context": segment.text
                    })

        return fillers

    def find_topic_changes(self, transcript: Transcript) -> List[Dict[str, Any]]:
        """
        Analyze transcript for topic changes
        Returns list of potential chapter boundaries
        """
        # Simple heuristic: long pauses or explicit transitions
        # In production, would use LLM for better detection
        changes = []

        for i, segment in enumerate(transcript.segments):
            if i == 0:
                changes.append({
                    "time": segment.start,
                    "type": "start",
                    "text": segment.text[:50]
                })
                continue

            prev = transcript.segments[i-1]
            gap = segment.start - prev.end

            # Gap > 2 seconds suggests topic change
            if gap > 2.0:
                changes.append({
                    "time": segment.start,
                    "type": "pause_break",
                    "gap_seconds": gap,
                    "text": segment.text[:50]
                })

        return changes
```

#### 2.2 Add audio export for transcription

**File**: `src/chat/python/tools.py`

Add new StateTools class:

```python
class StateTools:
    """Project state query tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def get_project_audio_path(self) -> Dict[str, Any]:
        """Get path to current project's audio for transcription"""
        # Note: This requires C++ backend support
        # For now, return placeholder indicating it needs implementation
        return {
            "success": False,
            "error": "Audio export for transcription not yet implemented in backend",
            "tool_missing": True
        }
```

**Note**: Full transcription requires exporting project audio to a temp file. This needs backend support via `IAgentStateReader`.

#### 2.3 Integrate transcription into orchestrator

**File**: `src/chat/python/orchestrator.py`

```python
# Add new Intent
class Intent(Enum):
    # ... existing
    ANALYZE = "analyze"
    GENERATE_TEXT = "generate_text"

# In OrchestratorAgent.__init__
from transcription_agent import TranscriptionAgent
self.transcription_agent = TranscriptionAgent()

# Add new handlers
def _handle_analyze_request(self, message: str, params: Dict) -> Dict[str, Any]:
    """Handle analysis requests (requires transcription)"""
    if not self.transcription_agent.is_available():
        return {
            "type": "message",
            "content": "Transcription is not available. Please set OPENAI_API_KEY."
        }

    # Get audio path (requires backend support)
    audio_result = self.tools.state.get_project_audio_path()
    if not audio_result.get("success"):
        return {
            "type": "message",
            "content": "Cannot access project audio for analysis. This feature requires backend support for audio export."
        }

    # Transcribe
    transcript_result = self.transcription_agent.transcribe_file(audio_result["path"])
    if not transcript_result.get("success"):
        return {"type": "message", "content": transcript_result["error"]}

    transcript = transcript_result["transcript"]

    # Perform requested analysis
    analysis_type = params.get("analysis_type", "summarize")

    if analysis_type == "find_filler":
        fillers = self.transcription_agent.find_filler_words(transcript)
        return self._format_filler_report(fillers)

    elif analysis_type == "find_issues":
        # Use LLM to analyze transcript
        return self._analyze_with_llm(transcript, "find issues")

    elif analysis_type == "summarize":
        return self._analyze_with_llm(transcript, "summarize")

    return {"type": "message", "content": "Unknown analysis type"}
```

**Success Criteria**:

#### Automated Verification:
- [ ] transcription_agent.py syntax valid
- [ ] TranscriptionAgent initializes without OpenAI key (graceful degradation)
- [ ] TranscriptionAgent initializes with OpenAI key

#### Manual Verification:
- [ ] "Summarize this episode" returns helpful message about needing audio export
- [ ] With mock audio file, transcription returns segments
- [ ] Filler word detection finds "um" and "uh" in transcript

---

### Phase 3: Content Generation & Analysis

**Goal**: Enable text generation features (show notes, summaries, social posts)

**Changes Required**:

#### 3.1 Create content_generator.py

**File**: `src/chat/python/content_generator.py`

```python
#!/usr/bin/env python3
"""
Content Generator Agent
Generates podcast-related content using LLM
"""

from typing import Dict, Any, Optional
from config import get_openai_api_key, is_openai_configured

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ContentGenerator:
    """Generate podcast content from transcripts"""

    PROMPTS = {
        "show_notes": """Generate professional podcast show notes from this transcript.
Include:
- Episode summary (2-3 sentences)
- Key topics discussed (bullet points)
- Notable quotes
- Timestamps for major sections

Transcript:
{transcript}""",

        "episode_description": """Write an engaging episode description for podcast platforms.
Keep it under 200 words. Make it compelling and SEO-friendly.

Transcript:
{transcript}""",

        "social_post": """Write a social media post promoting this podcast episode.
Platform: {platform}
Tone: Engaging, conversational
Length: Appropriate for {platform}
Include relevant hashtags.

Transcript excerpt:
{transcript}""",

        "chapter_markers": """Analyze this transcript and suggest chapter markers.
Return as a list with timestamps and titles.
Format: MM:SS - Chapter Title

Transcript:
{transcript}""",

        "summary": """Summarize this podcast episode in 3-5 sentences.
Focus on the main topics and key takeaways.

Transcript:
{transcript}"""
    }

    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE and is_openai_configured():
            self.client = OpenAI(api_key=get_openai_api_key())

    def is_available(self) -> bool:
        return self.client is not None

    def generate(self, content_type: str, transcript: str, **kwargs) -> Dict[str, Any]:
        """
        Generate content from transcript

        Args:
            content_type: Type of content (show_notes, episode_description, etc.)
            transcript: Full transcript text
            **kwargs: Additional parameters (e.g., platform for social posts)
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Content generation not available. Set OPENAI_API_KEY."
            }

        prompt_template = self.PROMPTS.get(content_type)
        if not prompt_template:
            return {
                "success": False,
                "error": f"Unknown content type: {content_type}"
            }

        # Format prompt
        prompt = prompt_template.format(transcript=transcript[:8000], **kwargs)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional podcast content creator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "content_type": content_type
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Generation failed: {str(e)}"
            }
```

#### 3.2 Update requirements.txt

**File**: `src/chat/python/requirements.txt`

```
openai>=1.0.0
python-dotenv>=1.0.0
```

**Success Criteria**:

#### Automated Verification:
- [ ] content_generator.py syntax valid
- [ ] All prompt templates are valid format strings

#### Manual Verification:
- [ ] "Write show notes" generates formatted show notes
- [ ] "Create LinkedIn post" generates platform-appropriate content
- [ ] Content is accurate to transcript (no hallucinations)

---

### Phase 4: Graceful Degradation & User Feedback

**Goal**: Handle missing tools gracefully with helpful messages

**Changes Required**:

#### 4.1 Add tool availability checker

**File**: `src/chat/python/tool_availability.py`

```python
#!/usr/bin/env python3
"""
Tool Availability Checker
Tracks which tools are available and provides helpful messages
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ToolStatus:
    available: bool
    tool_name: str
    reason: str
    workaround: str


TOOL_REGISTRY = {
    # Selection tools
    "select_time_range": ToolStatus(
        available=False,
        tool_name="Time-based Selection",
        reason="Backend tool for setting selection by timestamp not implemented",
        workaround="Manually select the time range in the timeline, then ask me to apply an effect"
    ),
    "select_all": ToolStatus(
        available=True,
        tool_name="Select All",
        reason="",
        workaround=""
    ),

    # Effect tools
    "noise_reduction": ToolStatus(
        available=True,
        tool_name="Noise Reduction",
        reason="Opens effect dialog (manual parameter setting required)",
        workaround=""
    ),
    "auto_apply_effect": ToolStatus(
        available=False,
        tool_name="Automatic Effect Application",
        reason="Effects open dialogs for user configuration",
        workaround="I'll open the effect dialog for you to configure and apply"
    ),

    # Analysis tools
    "silence_detection": ToolStatus(
        available=False,
        tool_name="Silence Detection",
        reason="No audio analysis backend available",
        workaround="I can analyze the transcript to find pauses in speech"
    ),
    "loudness_analysis": ToolStatus(
        available=False,
        tool_name="Loudness Analysis",
        reason="No audio metering backend available",
        workaround="Use the Normalize effect to set target loudness"
    ),

    # Label tools
    "create_label": ToolStatus(
        available=False,
        tool_name="Label Creation",
        reason="No label track write action available",
        workaround="I'll provide timestamps in chat that you can manually add as labels"
    ),

    # Transcription
    "transcribe": ToolStatus(
        available=True,  # Via Whisper API
        tool_name="Transcription",
        reason="Requires OPENAI_API_KEY and audio export support",
        workaround=""
    ),
}


def check_tool(tool_name: str) -> ToolStatus:
    """Get status of a tool"""
    return TOOL_REGISTRY.get(tool_name, ToolStatus(
        available=False,
        tool_name=tool_name,
        reason="Unknown tool",
        workaround="This feature may not be supported"
    ))


def get_unavailable_message(tool_name: str) -> str:
    """Get user-friendly message for unavailable tool"""
    status = check_tool(tool_name)
    if status.available:
        return ""

    msg = f"I can't {status.tool_name.lower()} automatically. {status.reason}."
    if status.workaround:
        msg += f"\n\n**Workaround**: {status.workaround}"

    return msg


def get_available_tools() -> List[str]:
    """Get list of available tool names"""
    return [name for name, status in TOOL_REGISTRY.items() if status.available]
```

#### 4.2 Update orchestrator for graceful handling

**File**: `src/chat/python/orchestrator.py`

Add to process_request:

```python
from tool_availability import check_tool, get_unavailable_message

def process_request(self, user_message: str) -> Dict[str, Any]:
    # ... parse intent with LLM
    intent, params = self._parse_intent_with_llm(user_message)

    # Check tool availability before planning
    required_tools = self._get_required_tools(intent, params)
    unavailable = [t for t in required_tools if not check_tool(t).available]

    if unavailable:
        # Some tools not available - provide helpful response
        messages = [get_unavailable_message(t) for t in unavailable]

        # Check if we can do anything useful
        available_actions = self._get_available_actions(intent, params)

        if available_actions:
            return {
                "type": "message",
                "content": f"I can partially help with this:\n\n" +
                          "\n".join(messages) +
                          f"\n\n**What I can do**: {', '.join(available_actions)}"
            }
        else:
            return {
                "type": "message",
                "content": "\n\n".join(messages)
            }

    # Continue with normal processing...
```

**Success Criteria**:

#### Automated Verification:
- [ ] tool_availability.py syntax valid
- [ ] All tools in registry have valid ToolStatus

#### Manual Verification:
- [ ] "Cut from 1:00 to 2:00" explains time selection is unavailable
- [ ] "Remove filler words" explains what's possible (detection) vs blocked (removal)
- [ ] Messages include workarounds

---

## Summary: Test Matrix Capabilities After Implementation

| Level | Total Tests | TOOL_AVAILABLE | TOOL_MISSING | PARTIAL |
|-------|-------------|----------------|--------------|---------|
| L1: Simple | 10 | 4 | 5 | 1 |
| L2: Intermediate | 8 | 2 | 4 | 2 |
| L3: Complex | 8 | 0 | 6 | 2 |
| L4: Advanced | 12 | 3 | 8 | 1 |
| L5: Content Gen | 5 | 5 | 0 | 0 |
| L6: Meta | 4 | 0 | 3 | 1 |
| **Total** | **47** | **14 (30%)** | **26 (55%)** | **7 (15%)** |

### Key Blockers (require backend changes)

1. **Time-based selection** - Blocks ~15 tests. Needs `set_time_selection(start_seconds, end_seconds)` action.
2. **Audio export for transcription** - Blocks all transcription features. Needs `IAgentStateReader` extension.
3. **Label track write** - Blocks chapter/marker features. Needs label creation action.
4. **Auto-apply effects** - Quality-of-life. Effects work but require dialog interaction.

### Fully Functional After This Plan

- OpenAI-powered intent parsing
- Conversation memory
- Content generation (show notes, descriptions, social posts)
- Graceful degradation with helpful messages
- Basic effect application (via dialogs)
- Undo/redo
- Playback control

---

## References

- Current chat implementation: `src/chat/python/orchestrator.py`
- Tool registry: `src/chat/python/tools.py`
- OpenAI config: `src/chat/python/config.py`
- C++ bridge: `src/chat/internal/pythonbridge.cpp`
