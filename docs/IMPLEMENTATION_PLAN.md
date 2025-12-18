# Sonos TTS Web Service - TDD Implementation Plan

## Project Overview
Convert the existing Sonos volume control script into a browser-based web service with ElevenLabs TTS integration, following Test-Driven Development practices.

---

## Architecture Summary

```
Frontend (Browser)
    ↕ WebSocket + REST API
FastAPI Backend
    ├── Sonos Service (async with thread pool)
    ├── TTS Service (ElevenLabs integration)
    ├── WebSocket Manager (real-time updates)
    └── Background Tasks (discovery, cleanup)
```

---

## Project Structure

```
TurnDownForWhat/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + lifespan events
│   ├── config.py                   # Settings (Pydantic BaseSettings)
│   ├── dependencies.py             # FastAPI dependencies (auth, etc.)
│   ├── models.py                   # Pydantic models for API
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── speakers.py             # Speaker endpoints
│   │   ├── tts.py                  # TTS endpoints
│   │   └── websocket.py            # WebSocket endpoint
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sonos_service.py        # Sonos operations (async)
│   │   ├── tts_service.py          # ElevenLabs integration
│   │   ├── websocket_manager.py    # WebSocket connection manager
│   │   ├── discovery_service.py    # Background speaker discovery
│   │   └── cleanup_service.py      # Audio file cleanup
│   │
│   └── utils/
│       ├── __init__.py
│       ├── network.py              # Local IP detection
│       ├── async_helpers.py        # asyncio.to_thread wrappers
│       └── errors.py               # Standard error response helpers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_config.py
│   ├── test_network.py
│   ├── test_utils.py
│   ├── test_sonos_service.py
│   ├── test_tts_service.py
│   ├── test_cleanup_service.py
│   ├── test_websocket_manager.py
│   ├── test_api_speakers.py
│   ├── test_api_tts.py
│   ├── test_websocket_api.py
│   ├── test_main.py
│   └── test_integration.py
│
├── static/
│   ├── audio/                      # Generated TTS files
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── app.js                  # Main frontend logic
│       └── websocket.js            # WebSocket client
│
├── templates/
│   └── index.html                  # Main dashboard
│
├── requirements.txt
├── requirements-dev.txt            # pytest, pytest-asyncio, etc.
├── .env.example
├── .env                            # gitignored
├── pytest.ini
└── README.md
```

---

## Work Packages (For Parallel Agent Execution)

### **Package A: Core Infrastructure & Configuration**
**Agent Focus:** Project setup, configuration, utilities
**Estimated Time:** 30 minutes

#### Tasks:
1. Create project structure (directories)
2. Write `app/config.py` with Pydantic BaseSettings
   - **Note:** Configure to load from `.env` file using `python-dotenv`
   - Include `ELEVENLABS_API_KEY`, `HOST`, `PORT`, optional `API_KEY` for auth
3. Write `app/utils/network.py` for local IP detection
4. Write `app/utils/async_helpers.py` for asyncio wrappers
5. Create `requirements.txt` and `requirements-dev.txt`
6. Create `.env.example` with all required environment variables
7. Write `pytest.ini` configuration
8. Define standard error response format for API consistency

#### Test Files:
- `tests/test_config.py` - Test settings loading from .env
- `tests/test_network.py` - Test IP detection
- `tests/test_utils.py` - Test error response format helper
- `tests/conftest.py` - Shared fixtures

#### TDD Approach:
- **Test First:** Write test for `get_local_ip()` that validates IP format
- **Implement:** Create function using `ifaddr` library
- **Refine:** Handle edge cases (no network, multiple interfaces)

---

### **Package B: Sonos Service Layer**
**Agent Focus:** Async Sonos operations with thread pool
**Estimated Time:** 1 hour

#### Tasks:
1. Write `app/services/sonos_service.py`
   - `async def discover_speakers()` (cached)
   - `async def get_speaker_status(ip: str)`
   - `async def set_speaker_volume(ip: str, volume: int)`
   - `async def fade_speaker_volume(ip: str, target: int, callback=None)`
   - `async def play_uri(ip: str, uri: str)`
   - `async def pause_speaker(ip: str)`
   - `async def stop_speaker(ip: str)`

2. Refactor existing `slowly_adjust_volume()` to async with callbacks

#### Test Files:
- `tests/test_sonos_service.py`
  - Mock `soco.SoCo` objects
  - Test async wrappers
  - Test fade algorithm with mocked speakers
  - Test error handling (unreachable speaker)
  - **Critical:** Test speaker becoming unreachable during volume fade
  - **Critical:** Test concurrent requests to same speaker (race conditions)

#### TDD Approach:
- **Test First:**
  ```python
  @pytest.mark.asyncio
  async def test_set_speaker_volume():
      # Given: Mock speaker
      # When: Set volume to 50
      # Then: speaker.volume should be 50
  ```
- **Implement:** Wrap with `asyncio.to_thread()`
- **Verify:** Run tests

#### Key Challenge:
Converting synchronous `soco` calls to async without blocking

---

### **Package C: TTS Service & File Management**
**Agent Focus:** ElevenLabs integration, audio generation, cleanup
**Estimated Time:** 45 minutes

#### Tasks:
1. Write `app/services/tts_service.py`
   - `async def generate_tts_audio(text: str, voice: str) -> str`
   - `async def get_available_voices() -> List[Voice]`
   - `def get_audio_url(filename: str, local_ip: str) -> str`

2. Write `app/services/cleanup_service.py`
   - `async def cleanup_old_audio_files(max_age_minutes: int)`
   - Background scheduler integration

#### Test Files:
- `tests/test_tts_service.py`
  - Mock ElevenLabs API
  - Test audio file creation
  - Test URL generation
  - Test error handling (API failure)
  - **Critical:** Test invalid/missing API key handling
  - **Critical:** Test rate limit error handling
- `tests/test_cleanup_service.py`
  - Test file age detection
  - Test deletion logic
  - **Critical:** Test file locking (deleting audio while being played)

#### TDD Approach:
- **Test First:**
  ```python
  @pytest.mark.asyncio
  async def test_generate_tts_creates_file(tmp_path):
      # Given: Text "Hello"
      # When: Generate TTS
      # Then: MP3 file exists in static/audio/
  ```
- **Implement:** ElevenLabs API call + file saving
- **Verify:** File exists and is valid MP3

---

### **Package D: WebSocket Manager & Real-time Updates**
**Agent Focus:** WebSocket connection management, broadcasting
**Estimated Time:** 45 minutes

#### Tasks:
1. Write `app/services/websocket_manager.py`
   - `class ConnectionManager` (singleton pattern)
   - `async def connect(websocket: WebSocket)`
   - `async def disconnect(websocket: WebSocket)`
   - `async def broadcast(message: dict)`
   - `async def send_to_client(websocket: WebSocket, message: dict)`

2. Implement message types:
   - `speaker_update`
   - `fade_progress`
   - `tts_started`
   - `error`

#### Test Files:
- `tests/test_websocket_manager.py`
  - Test connection/disconnection
  - Test broadcast to multiple clients
  - Test message serialization
  - Test error handling (disconnected client)

#### TDD Approach:
- **Test First:**
  ```python
  @pytest.mark.asyncio
  async def test_broadcast_sends_to_all_clients():
      # Given: 3 connected clients
      # When: Broadcast message
      # Then: All clients receive message
  ```
- **Implement:** ConnectionManager with broadcast logic
- **Verify:** All mock clients received message

---

### **Package E: API Endpoints (Speakers)**
**Agent Focus:** FastAPI routes for speaker control
**Estimated Time:** 45 minutes

#### Tasks:
1. Write `app/api/speakers.py`
   - `GET /api/speakers` - List all speakers
   - `GET /api/speakers/{ip}/status` - Get speaker status
   - `POST /api/speakers/{ip}/volume` - Set volume
   - `POST /api/speakers/{ip}/fade` - Fade volume
   - `POST /api/speakers/{ip}/play` - Resume playback
   - `POST /api/speakers/{ip}/pause` - Pause playback
   - `POST /api/speakers/{ip}/stop` - Stop playback
   - `POST /api/speakers/volume/all` - Set all volumes

2. Integrate with `sonos_service`
3. Add WebSocket updates for state changes

#### Test Files:
- `tests/test_api_speakers.py`
  - Test each endpoint with `TestClient`
  - Test validation (invalid IP, invalid volume)
  - Test standard error response format
  - Test error responses (speaker unreachable, invalid parameters)
  - Mock `sonos_service` methods

#### TDD Approach:
- **Test First:**
  ```python
  def test_get_speakers_returns_list(client):
      # When: GET /api/speakers
      # Then: Returns 200 with speaker list
      response = client.get("/api/speakers")
      assert response.status_code == 200
      assert isinstance(response.json(), list)
  ```
- **Implement:** Endpoint with service integration
- **Verify:** All tests pass

---

### **Package F: API Endpoints (TTS)**
**Agent Focus:** FastAPI routes for TTS
**Estimated Time:** 30 minutes

#### Tasks:
1. Write `app/api/tts.py`
   - `POST /api/tts/generate` - Generate and play TTS
   - `GET /api/tts/voices` - Get available voices
   - `POST /api/tts/play/{filename}` - Replay existing TTS

2. Integrate with `tts_service` and `sonos_service`
3. Add WebSocket updates for TTS events

#### Test Files:
- `tests/test_api_tts.py`
  - Test TTS generation endpoint
  - Test voice listing
  - Test speaker selection
  - Test error handling (empty text, invalid voice)

#### TDD Approach:
- **Test First:**
  ```python
  def test_generate_tts_returns_audio_url(client):
      # Given: Valid text and speaker
      # When: POST /api/tts/generate
      # Then: Returns audio URL
  ```
- **Implement:** Endpoint with full TTS flow
- **Verify:** Audio file created and URL returned

---

### **Package G: WebSocket API & Background Tasks**
**Agent Focus:** WebSocket endpoint, lifespan events
**Estimated Time:** 45 minutes

#### Tasks:
1. Write `app/api/websocket.py`
   - `@app.websocket("/ws")` endpoint
   - Handle client subscription
   - Process incoming messages
   - Error handling

2. Write `app/main.py` with lifespan events
   - **Ensure `static/audio/` directory exists on startup**
   - Start speaker discovery background task
   - Start cleanup background task
   - Initialize WebSocket manager
   - Mount static files and configure proper Content-Type headers

#### Test Files:
- `tests/test_websocket_api.py`
  - Test WebSocket connection
  - Test message handling
  - Test subscription flow
- `tests/test_main.py`
  - Test lifespan events
  - Test app initialization

#### TDD Approach:
- **Test First:**
  ```python
  def test_websocket_accepts_connection(client):
      # When: Connect to /ws
      # Then: Connection successful
  ```
- **Implement:** WebSocket endpoint
- **Verify:** Connection and message flow work

---

### **Package H: Frontend Development**
**Agent Focus:** HTML/CSS/JS interface
**Estimated Time:** 2-3 hours

#### Tasks:
1. Write `templates/index.html`
   - Semantic HTML structure
   - TailwindCSS integration
   - Component layout (TTS form, speaker cards)

2. Write `static/js/websocket.js`
   - WebSocket client connection
   - Reconnection logic
   - Message handling

3. Write `static/js/app.js`
   - API calls to backend
   - DOM manipulation
   - Event handlers
   - Real-time updates from WebSocket

4. Write `static/css/styles.css`
   - Custom styles beyond Tailwind
   - Animations for volume sliders

#### Test Approach:
- Manual testing in browser
- Optional: Add Playwright tests later

---

### **Package I: Integration Tests & Documentation**
**Agent Focus:** End-to-end tests, README
**Estimated Time:** 1.5-2 hours

#### Tasks:
1. Write `tests/test_integration.py`
   - Full flow: Discover → Fade → TTS → Play
   - Test WebSocket updates during operations
   - Test error recovery

2. Update `README.md`
   - Installation instructions
   - Configuration guide
   - API documentation
   - Architecture diagram

3. Create `.env.example` with all required variables

#### Test Files:
- `tests/test_integration.py`
  - End-to-end scenarios
  - Multi-speaker operations
  - Error scenarios

---

## Dependencies

### Production (`requirements.txt`)
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
soco==0.30.1
elevenlabs==0.2.24
python-dotenv==1.0.0
websockets==12.0
pydantic==2.5.0
pydantic-settings==2.1.0
apscheduler==3.10.4
ifaddr==0.2.0
jinja2==3.1.2
```

### Development (`requirements-dev.txt`)
```txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.26.0
black==23.12.1
ruff==0.1.9
mypy==1.7.1
```

---

## TDD Workflow

For each work package:

1. **RED:** Write failing test
   ```python
   def test_feature_should_work():
       # Given: Setup
       # When: Action
       # Then: Assert expected behavior
       assert False  # Initially fails
   ```

2. **GREEN:** Write minimal code to pass
   ```python
   def feature():
       return expected_result
   ```

3. **REFACTOR:** Improve code quality
   - Extract functions
   - Remove duplication
   - Add type hints

4. **REPEAT:** Next test

---

## Agent Coordination Strategy

### Parallel Execution:
- **Agents A, C, D** can work simultaneously (no dependencies)
- **Agent B** must complete before **E, F**
- **Agent G** needs **B, C, D** complete
- **Agent H** can work independently
- **Agent I** runs last (needs all others)

### Recommended Order:
```
Phase 1 (Parallel):  A, C, D
Phase 2 (Parallel):  B, H
Phase 3 (Parallel):  E, F
Phase 4 (Sequential): G
Phase 5 (Sequential): I
```

---

## Git Worktree Strategy

```bash
# Main branch: Keep stable code
main/

# Feature branch worktrees:
feature/infrastructure/     # Package A
feature/sonos-service/      # Package B
feature/tts-service/        # Package C
feature/websocket/          # Package D
feature/api-speakers/       # Package E
feature/api-tts/            # Package F
feature/app-main/           # Package G
feature/frontend/           # Package H
feature/integration/        # Package I
```

---

## Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific package tests
pytest tests/test_sonos_service.py -v

# Run async tests only
pytest -m asyncio

# Run with output
pytest -s
```

---

## Success Criteria

- [ ] All tests pass with >80% coverage
- [ ] Speaker discovery works and caches results
- [ ] Volume fading maintains S-curve smoothness
- [ ] TTS generates audio and plays on speakers
- [ ] WebSocket provides real-time updates
- [ ] Frontend UI is responsive and intuitive
- [ ] No blocking calls in async code
- [ ] Audio files cleaned up automatically
- [ ] API handles errors gracefully
- [ ] Documentation is complete

---

## Standard Error Response Format

All API endpoints should return errors in a consistent JSON format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "SPEAKER_UNREACHABLE",
  "timestamp": "2024-12-10T21:00:00Z"
}
```

**Common Error Codes:**
- `SPEAKER_UNREACHABLE` - Cannot connect to speaker
- `INVALID_VOLUME` - Volume not in range 0-100
- `TTS_GENERATION_FAILED` - ElevenLabs API error
- `INVALID_API_KEY` - Missing/invalid ElevenLabs key
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `FILE_NOT_FOUND` - Audio file doesn't exist
- `CONCURRENT_OPERATION` - Operation already in progress

Implement in `app/utils/errors.py` with helper functions.

---

## Critical Gemini Insights to Remember

1. **Always wrap `soco` calls with `asyncio.to_thread()`**
2. **Cache speaker discovery, refresh every 5 minutes**
3. **Use `ifaddr` for local IP detection**
4. **Sonos needs complete file URLs, not streaming**
5. **Add input validation for TTS text length**

---

## Estimated Total Time
- Development: ~8 hours
- Testing: ~2.5 hours
- Documentation: ~1.5 hours
**Total: ~12 hours** (across parallel agents, ~5-6 hours wall time with 20-30% buffer)
