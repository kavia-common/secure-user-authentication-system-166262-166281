#!/bin/bash
cd /home/kavia/workspace/code-generation/secure-user-authentication-system-166262-166281/authentication_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

