#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

# ── Global config ─────────────────────────────
: SC set width 80
: SC set height 14
: SC set type_speed 40
: SC set cmd_wait 300
: SC set exit_wait 800
: SC set input_wait 300
: SC set theme dark

# ANSI color helpers
: SC helpers

# ── Scene 1: login ────────────────────────────
# SC expect drives an interactive process via expect(1).
# Inputs typed by send appear as animated keystrokes in the cast.
: SC scene login

: SC expect ./fake-myapp <<'EOF'
expect "Email:"
send "dev@example.com\r"
expect "Password:"
send "secret\r"
expect eof
EOF

# ── Scene 2: deploy ───────────────────────────
# SC mock intercepts the command and returns fixed output.
# Reproducible on any machine — no real deploy needed.
: SC scene deploy

: SC mock myapp deploy --env staging <<EOF
Building image...
Running migrations... 3 applied
Deploying containers... done
${GREEN}✓${RESET} Live at ${CYAN}https://staging.myapp.io${RESET}
EOF

# ── Scene 3: status ───────────────────────────
# SC mock provides output. SC filter strips any real URLs.
# SC '\' emits a comment line as a typed prompt in the cast.
: SC scene status

: SC mock myapp status <<EOF
${BOLD}api${RESET}     ${GREEN}● running${RESET}  99.9% uptime
${BOLD}worker${RESET}  ${GREEN}● running${RESET}  99.9% uptime
${BOLD}db${RESET}      ${GREEN}● running${RESET}  healthy
EOF

: SC filter sed 's#https://[^ ]*\.myapp\.io#https://staging.myapp.io#g'
: SC '\' Check deployment health
