# AI Chat & Multi-Agent System Implementation Plan

## Architecture Decisions & Answers

### Python for AI - Feedback

**Pros:**
- Rich AI/LLM ecosystem (OpenAI SDK, LangChain, etc.)
- Faster development for AI logic
- Easy to iterate on prompts and agent logic
- Better tooling for debugging AI behavior

**Cons:**
- Requires IPC (Inter-Process Communication) between C++ and Python
- Additional complexity in deployment
- Need to manage Python environment

**Recommendation**: Use Python for AI with a well-defined IPC interface. This is the right choice for rapid AI development.

### Using IActionsDispatcher Directly

**What it entails:**
- Agents call `dispatcher->dispatch(actionCode, actionData)` directly
- Agents subscribe to `preDispatch()` and `postDispatch()` channels for feedback
- Agents check `actionEnabled(actionCode)` before dispatching
- Agents query `actionList()` to discover available tools

**Pros:**
- No abstraction layer - direct access to all functionality
- Simpler architecture - fewer moving parts
- Agents have full control
- Easier to debug - can see exactly what's being called

**Cons:**
- Agents need to understand C++ types (ActionCode, ActionData)
- No built-in validation or safety checks
- Agents must handle all error cases themselves
- Tight coupling to internal implementation

### Wrapper Layer - Pros & Cons

**Pros:**
- Type-safe Python-friendly interface
- Built-in validation and error handling
- Can add agent-specific features (logging, retry logic, etc.)
- Easier to test and mock
- Can provide higher-level abstractions (e.g., "applyEffectToSelection" instead of multiple steps)
- Can add safety checks (e.g., prevent destructive operations without confirmation)
- Easier to version and maintain API

**Cons:**
- Additional code to maintain
- Potential performance overhead
- Need to keep wrapper in sync with underlying actions
- More complex architecture

**Recommendation**: **Create a thin wrapper layer**. Benefits outweigh costs:
- Provides Python-friendly interface
- Adds safety and validation
- Enables higher-level operations
- Makes testing easier
- Can evolve independently

### Agent-Specific Interfaces

**Does it make sense?**

**Yes, but keep it minimal:**
- Create interfaces for state queries (read-only)
- Keep action dispatch unified through wrapper
- Agent-specific interfaces for:
  - `IAgentStateReader` - Read project/selection state
  - `IAgentActionExecutor` - Execute actions with validation
  - `IAgentFeedbackProvider` - Get visual feedback status

**Why:**
- Separates concerns (read vs. write)
- Makes testing easier (can mock state reader)
- Allows different implementations (real vs. test)
- Provides clear boundaries

---

## Implementation Order

### Phase 1: Infrastructure (Week 1-2)

#### 1.1 Module Structure
- [ ] Create `src/chat/` directory structure
- [ ] Set up CMakeLists.txt
- [ ] Create module files (chatmodule.cpp/h)
- [ ] Register module in main app

#### 1.2 Chat UI (QML)
- [ ] Create chat sidebar component (modeled after Cursor)
- [ ] Chat message list (user/assistant messages)
- [ ] Input field with send button
- [ ] Toggle button to show/hide sidebar
- [ ] Match existing UI styling
- [ ] Integration with appshell layout

#### 1.3 Python Bridge
- [ ] Create IPC mechanism (stdin/stdout, named pipes, or HTTP)
- [ ] Python service that receives requests
- [ ] C++ client that sends requests to Python
- [ ] Message serialization (JSON)
- [ ] Error handling and reconnection logic

#### 1.4 Tool Calling Infrastructure
- [ ] Create `IAgentActionExecutor` interface
- [ ] Implement wrapper around `IActionsDispatcher`
- [ ] Create `IAgentStateReader` interface
- [ ] Implement state reader using existing controllers
- [ ] Action validation layer
- [ ] Error handling and reporting

#### 1.5 Visual Feedback System
- [ ] Subscribe to `preDispatch()` and `postDispatch()` channels
- [ ] Create feedback event system
- [ ] UI components to show:
  - Action in progress indicators
  - Selection highlights
  - Dialog opening animations
  - Progress bars for long operations
- [ ] Integration with existing UI components

### Phase 2: Basic Orchestrator (Week 3-4)

#### 2.1 Orchestrator Agent (Python)
- [ ] Basic orchestrator that receives user requests
- [ ] Intent parsing (using OpenAI)
- [ ] Tool discovery (read from TOOL_CATALOG.md or API)
- [ ] Basic task breakdown
- [ ] Error handling and clarification requests

#### 2.2 Selection Agent (Python)
- [ ] Selection management logic
- [ ] Integration with `IAgentStateReader`
- [ ] Selection validation
- [ ] Context-aware selection (find clips, tracks, etc.)

#### 2.3 Effect Agent (Python)
- [ ] Effect application logic
- [ ] Effect parameter handling
- [ ] Integration with effect system
- [ ] Effect validation

#### 2.4 Agent Communication
- [ ] Agent-to-agent messaging
- [ ] Task delegation
- [ ] Result aggregation
- [ ] Error propagation

### Phase 3: Approval Workflow (Week 5)

#### 3.1 Preview System
- [ ] Generate previews for operations
- [ ] Show what will be affected
- [ ] Before/after comparisons where possible
- [ ] Inline preview in chat

#### 3.2 Approval UI
- [ ] Approve/Cancel buttons in chat
- [ ] Preview panels
- [ ] Step-by-step approval for multi-step operations
- [ ] Batch approval option

#### 3.3 Undo Integration
- [ ] Undo button after operations
- [ ] Undo stack management
- [ ] Visual feedback for undo

### Phase 4: Testing & Refinement (Week 6)

#### 4.1 Tool Testing
- [ ] Create test file based on TOOL_CATALOG.md
- [ ] Test each tool individually
- [ ] Verify visual feedback
- [ ] Test error cases

#### 4.2 Orchestrator Testing
- [ ] Test multi-tool operations
- [ ] Test error handling
- [ ] Test clarification requests
- [ ] Test approval workflow

#### 4.3 Integration Testing
- [ ] End-to-end user flows
- [ ] Complex scenarios
- [ ] Performance testing
- [ ] UI responsiveness

---

## Directory Structure

```
src/chat/
├── CMakeLists.txt
├── chatmodule.cpp
├── chatmodule.h
├── chattypes.h
├── internal/
│   ├── chatcontroller.cpp
│   ├── chatcontroller.h
│   ├── agentactionexecutor.cpp
│   ├── agentactionexecutor.h
│   ├── agentstatereader.cpp
│   ├── agentstatereader.h
│   ├── agentfeedbackprovider.cpp
│   ├── agentfeedbackprovider.h
│   ├── pythonbridge.cpp
│   └── pythonbridge.h
├── qml/
│   └── Audacity/
│       └── Chat/
│           ├── ChatSidebar.qml
│           ├── ChatMessageList.qml
│           ├── ChatInput.qml
│           ├── ApprovalPanel.qml
│           └── PreviewPanel.qml
├── python/
│   ├── agent_service.py
│   ├── orchestrator.py
│   ├── selection_agent.py
│   ├── effect_agent.py
│   ├── tools.py
│   └── requirements.txt
├── tests/
│   ├── tool_tests.md
│   ├── orchestrator_tests.md
│   └── test_helpers.py
├── TOOL_CATALOG.md
└── IMPLEMENTATION_PLAN.md
```

---

## Key Interfaces

### IAgentActionExecutor

```cpp
class IAgentActionExecutor {
public:
    virtual Ret executeAction(const ActionCode& code, const ActionData& data = {}) = 0;
    virtual bool isActionEnabled(const ActionCode& code) const = 0;
    virtual ActionCodeList availableActions() const = 0;
    virtual async::Channel<ActionCode> actionCompleted() const = 0;
    virtual async::Channel<ActionCode, Ret> actionFailed() const = 0;
};
```

### IAgentStateReader

```cpp
class IAgentStateReader {
public:
    // Selection state
    virtual TrackIdList selectedTracks() const = 0;
    virtual ClipKeyList selectedClips() const = 0;
    virtual secs_t selectionStartTime() const = 0;
    virtual secs_t selectionEndTime() const = 0;
    
    // Project state
    virtual TrackList trackList() const = 0;
    virtual secs_t totalTime() const = 0;
    
    // Clip queries
    virtual ClipKeyList clipsOnTrack(TrackId trackId) const = 0;
    virtual Clip clip(const ClipKey& key) const = 0;
    
    // Notifications
    virtual async::Channel<> stateChanged() const = 0;
};
```

### IAgentFeedbackProvider

```cpp
class IAgentFeedbackProvider {
public:
    virtual void highlightSelection(const SelectionInfo& info) = 0;
    virtual void showProgress(const std::string& message, double progress) = 0;
    virtual void showDialog(const std::string& dialogType) = 0;
    virtual void clearHighlights() = 0;
};
```

---

## Python Service Structure

### agent_service.py (Main entry point)
- Receives requests from C++
- Routes to appropriate agent
- Handles tool calling
- Returns results

### orchestrator.py
- Main orchestration logic
- Intent parsing
- Task breakdown
- Agent coordination

### selection_agent.py
- Selection management
- Context-aware selection finding
- Selection validation

### effect_agent.py
- Effect application
- Parameter handling
- Effect validation

### tools.py
- Tool definitions (from TOOL_CATALOG.md)
- Tool calling helpers
- Parameter validation

---

## Testing Strategy

### Tool Tests (tool_tests.md)

For each tool in TOOL_CATALOG.md:
1. **Basic usage test**: Can the tool be called successfully?
2. **Parameter validation**: Are parameters validated correctly?
3. **Context requirements**: Does it fail gracefully when context is missing?
4. **Visual feedback**: Does visual feedback appear?
5. **Error handling**: Are errors handled appropriately?

Example:
```markdown
## Test: split

### Setup
- Create project with one track
- Add clip to track
- Select clip

### Test 1: Basic split
- Call `split` action
- **Expected**: Clip splits into two
- **Visual**: Split animation appears

### Test 2: No selection
- Clear selection
- Call `split` action
- **Expected**: Action fails gracefully
- **Error**: "No clip selected"

### Test 3: Multiple clips
- Select multiple clips
- Call `split` action
- **Expected**: All clips split
```

### Orchestrator Tests (orchestrator_tests.md)

Test multi-tool operations:
1. **Simple chain**: Selection → Effect
2. **Complex chain**: Multiple selections → Multiple effects
3. **Error recovery**: Handle failures mid-chain
4. **Clarification**: Request clarification when needed
5. **Approval**: Approval workflow for destructive operations

Example:
```markdown
## Test: "Remove noise from first 30 seconds"

### Expected flow
1. Orchestrator parses request
2. Selection agent: Select 0:00-0:30
3. Effect agent: Apply noise reduction
4. Visual feedback at each step
5. Approval requested before effect application

### Verification
- Selection appears on timeline
- Noise reduction dialog opens
- Approval requested
- After approval, effect applies
- Visual feedback throughout
```

---

## Next Steps

1. **Start with Phase 1.1**: Create module structure
2. **Then Phase 1.2**: Build chat UI (most visible progress)
3. **Then Phase 1.3**: Python bridge (enables AI functionality)
4. **Then Phase 1.4**: Tool calling (enables actions)
5. **Then Phase 1.5**: Visual feedback (completes UX)

This order prioritizes user-visible features first, then functionality.

