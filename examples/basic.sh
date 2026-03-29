#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

# ----------------------------------------
# Global config
# ----------------------------------------
: SC set type_speed 40
: SC set cmd_wait 80
: SC set exit_wait 120
: SC set width 80
: SC set height 24

# ----------------------------------------
# Scene — Intro
# ----------------------------------------
: SC scene intro

: SC record pause
GREETING="Hello from scriptcast"
: SC record resume

echo "$GREETING"
echo "Generating terminal demos from shell scripts."

# ----------------------------------------
# Scene — Mock
# ----------------------------------------
: SC scene mock

: SC mock deploy <<'EOF'
Deploying to production...
Build: OK
Tests: OK
Deploy: OK
EOF

# ----------------------------------------
# Scene — Filter
# ----------------------------------------
: SC scene filter

: SC filter sed 's#/workspaces/scriptcast#<project>#g'

echo "Project root:"
pwd
