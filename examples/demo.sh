#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

: SC set width 80
: SC set height 18
: SC set type_speed 40
: SC set cmd_wait 80
: SC set prompt "$ "

# ── Scene: demo ───────────────────────────────
: SC scene demo

: SC mock scriptcast basic.sh <<'EOF'
Recording basic.sh...
Recorded: examples/basic.sc
Generated: examples/intro.cast
Generated: examples/mock.cast
Generated: examples/expect.cast
Generated: examples/filter.cast
Generated: examples/sleep.cast
Generated: examples/comment.cast
EOF

scriptcast basic.sh
