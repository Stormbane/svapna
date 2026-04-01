#!/bin/bash
# Svapna Autonomous Build Script
# Runs Claude Code in a loop to implement features from feature_list.json
#
# Usage:
#   cd /c/Projects/svapna
#   bash scripts/autonomous_build.sh
#
# Prerequisites:
#   - Claude Code CLI installed and authenticated
#   - ANTHROPIC_API_KEY set (for dream generation API calls in tests)
#   - jq installed (for JSON parsing)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

MAX_ITERATIONS=50
BUDGET_PER_ITERATION=10
LOG_DIR="$PROJECT_DIR/logs/autonomous"
mkdir -p "$LOG_DIR"

echo "=== Svapna Autonomous Build ==="
echo "Project: $PROJECT_DIR"
echo "Max iterations: $MAX_ITERATIONS"
echo "Budget per iteration: \$$BUDGET_PER_ITERATION"
echo "Logs: $LOG_DIR"
echo ""

# Check prerequisites
if ! command -v claude &> /dev/null; then
    echo "Error: claude CLI not found"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: jq not found. Install with: choco install jq"
    exit 1
fi

if [ ! -f "feature_list.json" ]; then
    echo "Error: feature_list.json not found"
    exit 1
fi

# Show initial state
completed=$(jq '.progress.completed' feature_list.json)
total=$(jq '.progress.total' feature_list.json)
echo "Starting progress: $completed / $total features"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    # Re-read progress each iteration
    completed=$(jq '.progress.completed' feature_list.json)
    total=$(jq '.progress.total' feature_list.json)

    if [ "$completed" -ge "$total" ]; then
        echo "All features complete!"
        break
    fi

    # Get next pending feature
    next_feature=$(jq -r '[.features[] | select(.status == "pending")][0].title // "none"' feature_list.json)
    next_id=$(jq -r '[.features[] | select(.status == "pending")][0].id // 0' feature_list.json)

    if [ "$next_feature" = "none" ] || [ "$next_id" = "0" ]; then
        echo "No pending features found. Done!"
        break
    fi

    echo "=== Iteration $i: Feature #$next_id - $next_feature ==="
    timestamp=$(date +%Y%m%d_%H%M%S)
    log_file="$LOG_DIR/iteration_${i}_feature_${next_id}_${timestamp}.log"

    # Run Claude in headless mode
    claude -p "$(cat <<PROMPT
You are working on the Svapna project - an AI dreaming system.

Read feature_list.json to find the next pending feature (feature #$next_id: "$next_feature").

Read the feature's description, test_cases, and files list carefully.
Also read the existing code in src/svapna/ to understand patterns and conventions.
Read CLAUDE.md for project conventions.

Implement the feature:
1. Create all files listed in the feature's "files" array
2. Follow the patterns established in existing code (see src/svapna/consolidate/ for examples)
3. Write comprehensive tests that cover all test_cases listed
4. Run the tests with: python -m pytest tests/ -v
5. If tests fail, fix the code and re-test (up to 3 attempts)
6. Once tests pass, update feature_list.json:
   - Set this feature's status to "completed"
   - Increment progress.completed by 1
7. Commit the changes with a descriptive message

Important:
- Use the existing code style (type hints, dataclasses, Path objects)
- Import from svapna.consolidate.ingest and svapna.consolidate.memories for shared types
- Use Pydantic for config/schema validation where specified
- For API calls (Anthropic), use the anthropic library already in dependencies
- Mock external API calls in tests (don't make real API calls in tests)
- Keep the code clean and well-typed

Do NOT:
- Modify existing working code unless the feature requires it
- Add dependencies not in pyproject.toml (propose them if needed)
- Skip writing tests
- Mark a feature complete if tests are failing
PROMPT
)" \
    --dangerously-skip-permissions \
    --effort high \
    2>&1 | tee "$log_file"

    echo ""
    echo "--- Iteration $i complete ---"

    # Show updated progress
    completed=$(jq '.progress.completed' feature_list.json)
    echo "Progress: $completed / $total"
    echo ""

    # Brief pause between iterations
    sleep 5
done

# Final summary
echo ""
echo "=== Build Summary ==="
completed=$(jq '.progress.completed' feature_list.json)
total=$(jq '.progress.total' feature_list.json)
echo "Features completed: $completed / $total"
echo ""
jq -r '.features[] | "  [\(.status)] #\(.id): \(.title)"' feature_list.json
