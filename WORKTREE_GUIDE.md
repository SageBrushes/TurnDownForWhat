# Git Worktree Setup for Parallel Development

## Overview

This project uses **git worktrees** to enable multiple agents to work on different features simultaneously without conflicts. Each worktree is a separate working directory with its own branch.

## Worktree Structure

```
TurnDownForWhat/               # Main repo (develop branch)
TurnDownForWhat-worktrees/     # Parallel development directories
  ├── infrastructure/          # Package A: Core infrastructure
  ├── sonos-service/           # Package B: Sonos service layer
  ├── tts-service/             # Package C: TTS & cleanup
  ├── websocket/               # Package D: WebSocket manager
  ├── api-speakers/            # Package E: Speaker API endpoints
  ├── api-tts/                 # Package F: TTS API endpoints
  ├── app-main/                # Package G: Main app & lifespan
  ├── frontend/                # Package H: HTML/CSS/JS
  └── integration/             # Package I: Integration tests
```

## Work Package Assignments

### Phase 1 (Parallel) - Can start immediately:
- **infrastructure** → Package A (Core setup, config, utils)
- **tts-service** → Package C (ElevenLabs integration)
- **websocket** → Package D (WebSocket manager)

### Phase 2 (Parallel) - After Phase 1 complete:
- **sonos-service** → Package B (Async Sonos operations)
- **frontend** → Package H (UI development)

### Phase 3 (Parallel) - After Package B complete:
- **api-speakers** → Package E (Speaker endpoints)
- **api-tts** → Package F (TTS endpoints)

### Phase 4 (Sequential) - After Packages B, C, D complete:
- **app-main** → Package G (Main app initialization)

### Phase 5 (Sequential) - After all others:
- **integration** → Package I (Integration tests & docs)

## Commands for Each Agent

### View all worktrees:
```bash
git worktree list
```

### Navigate to a worktree:
```bash
cd /Users/bigmachine/TurnDownForWhat-worktrees/<worktree-name>
```

### Check current branch:
```bash
git branch --show-current
```

### Commit changes:
```bash
git add .
git commit -m "Your commit message"
```

### Push to remote:
```bash
git push -u origin <branch-name>
```

### Merge to develop (when ready):
```bash
# From main repo
cd /Users/bigmachine/TurnDownForWhat
git checkout develop
git merge feature/<feature-name>
```

## Agent Workflow

Each agent should follow this workflow:

1. **Navigate to assigned worktree**:
   ```bash
   cd /Users/bigmachine/TurnDownForWhat-worktrees/<your-worktree>
   ```

2. **Read the implementation plan**:
   ```bash
   cat IMPLEMENTATION_PLAN.md
   ```
   Find your Package section (A-I)

3. **Follow TDD approach**:
   - Write failing tests first (RED)
   - Implement code to pass tests (GREEN)
   - Refactor and improve (REFACTOR)

4. **Run tests frequently**:
   ```bash
   source venv/bin/activate
   pytest tests/test_<your_module>.py -v
   ```

5. **Commit when tests pass**:
   ```bash
   git add .
   git commit -m "feat: implement <feature>"
   ```

6. **Push to remote** (optional):
   ```bash
   git push -u origin feature/<feature-name>
   ```

7. **Signal completion** when package is done

## Merging Strategy

### Option 1: Merge to develop as packages complete
```bash
cd /Users/bigmachine/TurnDownForWhat
git checkout develop
git merge feature/infrastructure --no-ff
git merge feature/tts-service --no-ff
# etc.
```

### Option 2: Create PR for each feature branch
```bash
gh pr create --base develop --head feature/infrastructure --title "Package A: Core Infrastructure"
```

## Dependencies Between Packages

**Important:** Some packages depend on others:

- **Package E & F** require **Package B** (sonos_service)
- **Package G** requires **Packages B, C, D**
- **Package I** requires **all others**

Agents working on dependent packages should:
1. Wait for prerequisite packages to complete
2. Pull latest from develop: `git pull origin develop`
3. Merge develop into their feature branch: `git merge develop`

## Cleanup (When Done)

Remove worktrees:
```bash
cd /Users/bigmachine/TurnDownForWhat
git worktree remove ../TurnDownForWhat-worktrees/infrastructure
git worktree remove ../TurnDownForWhat-worktrees/sonos-service
# ... etc for all worktrees
```

Or remove all at once:
```bash
cd /Users/bigmachine/TurnDownForWhat
for dir in ../TurnDownForWhat-worktrees/*; do
  git worktree remove "$dir"
done
```

## Tips for Parallel Development

1. **Communicate**: Let other agents know when you complete a package
2. **Test early and often**: Don't wait until the end to run tests
3. **Keep commits atomic**: One logical change per commit
4. **Follow the plan**: Stick to your assigned Package tasks
5. **Update develop**: Merge completed packages back to develop promptly

## Current Status

All worktrees created and ready for development!

Check: `git worktree list`
