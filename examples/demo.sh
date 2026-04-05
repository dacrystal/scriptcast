#!/usr/bin/env scriptcast --directive-prefix SC --trace-prefix +

: SC set width 80
: SC set height 10
: SC set type_speed 40
: SC set cmd_wait 80
: SC set cr_delay 10
: SC set prompt "$ "

# ── Scene: demo ───────────────────────────────
: SC scene demo

: SC filter sed "s#uv run ##g"
uv run scriptcast showcase.sh
