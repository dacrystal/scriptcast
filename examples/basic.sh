#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

# ----------------------------------------
# Global config
# ----------------------------------------
: SC set type_speed 40
: SC set word_speed 100
: SC set cmd_wait 500
: SC set exit_wait 1000
: SC set width 80
: SC set height 10
: SC set terminal-theme dark
: SC set input_wait 300
: SC set enter_wait 100

# ----------------------------------------
# Scene — Intro
# ----------------------------------------
: SC scene intro

: SC record pause
GREETING="Hello from scriptcast"
: SC record resume

echo "$GREETING"
echo -e "\x1b[92mGenerating terminal demos from shell scripts.\x1b[0m"

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
# Scene — expect
# ----------------------------------------
: SC scene expect

: SC expect ./fake-db <<'EOF'
expect "Password:"
send "secret\r"
expect "mysql>"
send "show databases;\r"
expect "mysql>"
send "exit\r"
expect eof
EOF

# ----------------------------------------
# Scene — Filter
# ----------------------------------------
: SC scene filter

: SC filter sed "s#$PWD#<project>#g"
: SC filter-add sed "s#/home/#/users/#g"

echo "Project root:"
pwd
echo "$HOME"

# ----------------------------------------
# Scene — sleep
# ----------------------------------------
: SC scene sleep

: SC '\' Pausing between lines...
echo "Before pause"
: SC sleep 800
echo "After pause"

# ----------------------------------------
# Scene — Comment
# ----------------------------------------
: SC scene comment

: SC \\ This is a comment
echo "Comments appear as cmd events in the cast"
