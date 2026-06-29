#!/bin/bash
set -e

REPO="ayub30/cv-talent-intelligence-app"
MAX_ITERATIONS=${1:-10}

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  echo "=== Iteration $i / $MAX_ITERATIONS ==="

  result=$(claude --permission-mode bypassPermissions -p \
    "You are working on the GitHub repo $REPO located in the current directory.

    1. Run: gh issue list --repo $REPO --state open --json number,title,body,labels --limit 20
    2. If no open issues exist, output <promise>COMPLETE</promise> and stop.
    3. Pick the highest priority open issue (lowest number first).
    4. Implement the feature/fix described in the issue.
    5. Run tests if they exist.
    6. Commit your changes referencing the issue: 'feat: <description> (closes #N)', do not put authored by claude or any claude watermark in the commit message.
    7. Push the commit.
    8. Close the issue: gh issue close N --repo $REPO --comment 'Implemented in <commit hash>'
    9. ONLY WORK ON ONE ISSUE.
    If all issues are done, output <promise>COMPLETE</promise>.")

  echo "$result"

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "All issues complete after $i iterations."
    exit 0
  fi

  sleep 10
done

echo "Reached max iterations ($MAX_ITERATIONS)."

