#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

: SC set width 80
: SC set height 10
: SC set type_speed 40
: SC set cmd_wait 80
: SC set prompt "$ "

# ── Scene: demo ───────────────────────────────
: SC scene demo

: SC mock scriptcast <<'EOF'
Recording examples/showcase.sh...
  Recorded:  examples/showcase.sc
  Generated: examples/showcase.cast
EOF

: SC filter sed "s#uv run ##g"
uv run scriptcast export showcase.sh
