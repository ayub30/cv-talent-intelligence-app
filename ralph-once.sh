#!/bin/bash

REPO="ayub30/cv-talent-intelligence-app"

claude --permission-mode bypassPermissions -p \
"You are working on the GitHub repo $REPO located in the current directory.

1. Run: gh issue list --repo $REPO --state open --json number,title,body,labels --limit 20
2. Pick the highest priority open issue (lowest number first).
3. Implement the feature/fix described in the issue.
4. Run tests if they exist.
5. Commit your changes referencing the issue: 'feat: <description> (closes #N)',do not put authored by claude or any claude watermark in the commit message.
6. Push the commit.
7. Close the issue: gh issue close N --repo $REPO --comment 'Implemented in <commit hash>'
8. ONLY DO ONE ISSUE AT A TIME."
