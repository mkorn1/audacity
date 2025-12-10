# AI Chat Service - Python Agents

This directory contains the Python-based AI agents for the Audacity chat feature.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. OpenAI API Key (Optional)

The chat service currently works with **keyword-based intent parsing** (no API key needed). However, for better intent understanding, you can optionally configure OpenAI integration.

#### Option A: Environment Variable (Recommended)

**macOS/Linux:**
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=sk-your-api-key-here
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-your-api-key-here"
```

#### Option B: Add to Shell Profile

Add to `~/.zshrc`, `~/.bashrc`, or `~/.profile`:
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

Then reload:
```bash
source ~/.zshrc  # or ~/.bashrc
```

#### Option C: Set in IDE/Editor

If running from an IDE, set the environment variable in the run configuration.

### 3. Get an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new API key
4. Copy the key (starts with `sk-`)
5. Set it as the `OPENAI_API_KEY` environment variable

## Current Status

- **Without API Key**: Uses keyword-based intent parsing (works immediately)
- **With API Key**: Will use OpenAI for better intent understanding (when implemented)

## Testing

The service communicates via stdin/stdout with the C++ application. To test manually:

```bash
python3 agent_service.py
```

Then send JSON messages via stdin:
```json
{"type": "message", "message": "select the first 30 seconds"}
```

## Architecture

- `agent_service.py` - Main entry point, handles IPC with C++
- `orchestrator.py` - Main orchestration logic, intent parsing
- `selection_agent.py` - Selection management
- `effect_agent.py` - Effect application
- `tools.py` - Tool execution wrapper
- `config.py` - Configuration management


