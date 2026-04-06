#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

# ── Global config ─────────────────────────────
: SC set width 80
: SC set height 8
: SC set type_speed 40
: SC set cmd_wait 300
: SC set exit_wait 800
: SC set input_wait 300
: SC set enter_wait 100
: SC helpers

# ── Scene: intro ──────────────────────────────
# Use SC record pause/resume to hide setup commands that
# should not appear in the cast (env vars, config, etc.).
: SC scene intro

: SC record pause
APP_NAME="scriptcast"
: SC record resume

echo "Welcome to $APP_NAME"
echo "${GREEN}Generate terminal demos from shell scripts.${RESET}"

# ── Scene: mock ───────────────────────────────
# SC mock <cmd> intercepts any call to <cmd> and returns
# the heredoc body as output. Use this for slow, side-effectful,
# or non-deterministic commands (deploy, network calls, etc.).
: SC scene mock

: SC mock deploy <<EOF
Deploying to production...
Build:   ${GREEN}OK${RESET}
Tests:   ${GREEN}OK${RESET}
Deploy:  ${GREEN}OK${RESET}  →  https://myapp.io
EOF


# ── Scene: expect ─────────────────────────────
# SC expect <binary> drives an interactive process with expect(1).
# Inputs from send appear as animated keystrokes. Silent reads
# (read -rs) produce *** masking in the cast.
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

# ── Scene: filter ─────────────────────────────
# SC filter pipes all subsequent output through a shell command.
# SC filter-add appends to the filter chain without replacing it.
# Use this to scrub real paths, hostnames, or credentials.
: SC scene filter

: SC filter sed "s#$PWD#<project>#g"
: SC filter-add sed "s#/home/#/users/#g"

echo "Project root:"
pwd
echo "$HOME"

# ── Scene: comment ────────────────────────────
# SC '\' <text> emits a comment line that appears as a typed
# prompt in the cast — useful for narrating steps.
: SC scene comment

: SC '\' Running integration tests...
echo "All 42 tests passed."

# ── Scene: sleep ──────────────────────────────
# SC sleep <ms> inserts a pause in the generated cast.
# Use it to let output breathe or emphasise a transition.
: SC scene sleep

echo "Compiling..."
: SC sleep 800
echo "Done in 1.2s."

# ── Scene: word_speed ─────────────────────────
# SC set word_speed adds an extra pause after each space,
# making commands appear to be typed more deliberately.
# Default is the same as type_speed (no extra gap).
: SC scene word_speed

: SC set word_speed 120
echo "This line types with a longer pause between each word."

# ── Scene: record ─────────────────────────────
# SC record pause stops capturing. Commands still execute,
# but their output is invisible in the cast. Resume to continue.
: SC scene record

: SC record pause
DB_URL="postgres://user:secret@localhost/mydb"
: SC record resume

echo "Connecting to database..."
echo "Connected."
