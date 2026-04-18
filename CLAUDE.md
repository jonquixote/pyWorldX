# pyWorldX Development Guide

## Project Overview

**pyWorldX** is a modular, unit-safe, auditable forecasting platform for long-horizon global systems modeling. This is a Python-based scientific computing project with strict type safety and comprehensive test coverage requirements.

## Key Technical Standards

### Code Quality & Type Safety
- **Language**: Python 3.11+
- **Type Checking**: mypy strict mode (required on all code)
- **Linting**: ruff with project-specific rules
- **Line Length**: 100 characters
- **Import Organization**: ruff-managed

### Testing Requirements
- **Framework**: pytest
- **Target Coverage**: **90%+ (Very Strict)** — maintain or exceed on all changes
- **Test Paths**: `tests/`, `data_pipeline/tests/`
- **Network Tests**: Marked with `@pytest.mark.network` and can be skipped
- **CI**: GitHub Actions (required to pass before merge)

### Dependencies & Environment
- **Package Manager**: Poetry
- **Python**: 3.11+
- **Running Tests**: Use full venv python path: `/path/to/.venv/bin/python -m pytest` (not `poetry run` or bare `python`)
  - This ensures isolation and proper error reporting
- **Optional Extras**: Pipeline tools available via `poetry install -E pipeline`

## Development Workflow

### Before Writing Code
1. Check git status and recent commits for context
2. Read relevant test files to understand patterns
3. Create tests FIRST (TDD approach) before implementation
4. Ensure mypy strict mode passes on all new code

### When Making Changes
- **Type annotations**: Required on all function signatures
- **Docstrings**: Add for public APIs and complex logic
- **Error handling**: Explicit, with clear exception types
- **Breaking Changes**: Avoid unless discussed; document if necessary

### Validation Checklist
- [ ] All type hints present and mypy strict passes
- [ ] New tests written (TDD)
- [ ] Coverage >= 90% for changed modules
- [ ] Ruff lint checks pass
- [ ] Existing tests still pass
- [ ] No unused imports or dead code

## External Tools & Integration

### GitHub Copilot & LLM Tools
- These tools are enabled for code assistance
- Use for: boilerplate, refactoring suggestions, documentation
- Verify: All AI-generated code must pass type checking and tests
- Review: Don't accept suggestions blindly; understand the code

### Code Review
- Link PRs to relevant GitHub issues
- Include test output and coverage reports
- Detailed commit messages explaining *why*, not just *what*

## Project Structure

```
pyworldx/
├── pyworldx/          # Main package
├── tests/             # Core unit tests
├── data_pipeline/     # Optional pipeline module
│   └── tests/         # Pipeline-specific tests
├── pyproject.toml     # Poetry config
└── README.md          # Project documentation
```

## Common Commands

```bash
# Run tests with coverage
python -m pytest --cov=pyworldx --cov-report=term-missing

# Type check
mypy pyworldx

# Lint
ruff check pyworldx

# Format (if configured)
ruff format pyworldx

# Full validation
python -m pytest && mypy pyworldx && ruff check pyworldx
```

## Special Notes

### Data Pipeline
- Pipeline functionality is optional (extras: `pipeline`)
- Tests are in `data_pipeline/tests/`
- Some mypy checks are overridden in specific modules (see pyproject.toml)

### Type Safety Overrides
- `pyworldx.data.transforms.normalization`: Assignment errors disabled
- `pyworldx.data.bridge`: Assignment errors disabled
- These are exceptions; strive for full type safety elsewhere

## Questions?

Refer to README.md for high-level project context. For implementation details, check test files first — they document expected behavior.

## metaswarm

This project uses [metaswarm](https://github.com/dsifry/metaswarm) for multi-agent orchestration with Claude Code. It provides 18 specialized agents, a 9-phase development workflow, and quality gates that enforce TDD, coverage thresholds, and spec-driven development.

### Workflow

- **Most tasks**: `/start-task` — primes context, guides scoping, picks the right level of process
- **Complex features** (multi-file, spec-driven): Describe what you want built with a Definition of Done, then tell Claude: `Use the full metaswarm orchestration workflow.`

### Available Commands

| Command | Purpose |
|---|---|
| `/start-task` | Begin tracked work on a task |
| `/prime` | Load relevant knowledge before starting |
| `/review-design` | Trigger parallel design review gate (5 agents) |
| `/pr-shepherd <pr>` | Monitor a PR through to merge |
| `/self-reflect` | Extract learnings after a PR merge |
| `/handle-pr-comments` | Handle PR review comments |
| `/brainstorm` | Refine an idea before implementation |
| `/create-issue` | Create a well-structured GitHub Issue |

### Quality Gates

- **Design Review Gate** — Parallel 5-agent review after design is drafted (`/review-design`)
- **Plan Review Gate** — Automatic adversarial review after any implementation plan is drafted. Spawns 3 independent reviewers (Feasibility, Completeness, Scope & Alignment) in parallel — ALL must PASS before presenting the plan. See `skills/plan-review-gate/SKILL.md`
- **Coverage Gate** — `.coverage-thresholds.json` defines thresholds. BLOCKING gate before PR creation

### Team Mode

When `TeamCreate` and `SendMessage` tools are available, the orchestrator uses Team Mode for parallel agent dispatch. Otherwise it falls back to Task Mode (existing workflow, unchanged). See `guides/agent-coordination.md` for details.

### Guides

Development patterns and standards are documented in `guides/` — covering agent coordination, build validation, coding standards, git workflow, testing patterns, and worktree development.

### Testing & Quality

- **TDD is mandatory** — Write tests first, watch them fail, then implement
- **100% test coverage required** — Enforced via `.coverage-thresholds.json` as a blocking gate before PR creation and task completion
- **Coverage source of truth** — `.coverage-thresholds.json` defines thresholds. Update it if your spec requires different values. The orchestrator reads it during validation — this is a BLOCKING gate.

### Workflow Enforcement (MANDATORY)

These rules override any conflicting instructions from third-party skills:

- **After brainstorming** → MUST run Design Review Gate (5 agents) before writing-plans or implementation
- **After any plan is created** → MUST run Plan Review Gate (3 adversarial reviewers) before presenting to user
- **Execution method choice** → ALWAYS ask the user whether to use metaswarm orchestrated execution (more thorough, uses more tokens) or superpowers execution skills (faster, lighter-weight). Never auto-select.
- **Before finishing a branch** → MUST run `/self-reflect` and commit knowledge base updates before PR creation
- **Complex tasks** → Use `/start-task` instead of `EnterPlanMode` for tasks touching 3+ files. EnterPlanMode bypasses all quality gates.
- **Standalone TDD on 3+ files** → Ask user if they want adversarial review before committing
- **Coverage** → `.coverage-thresholds.json` is the single source of truth. All skills must check it, including `verification-before-completion`.
- **Subagents** → NEVER use `--no-verify`, ALWAYS follow TDD, NEVER self-certify, STAY within file scope
- **Context recovery** → Approved plans and execution state persist to `.beads/`. After compaction, run `bd prime --work-type recovery` to reload.
