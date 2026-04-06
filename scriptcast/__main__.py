# scriptcast/__main__.py
import json
import logging
import os
import platform
import shlex
import shutil
import sys
import tempfile
import urllib.request
import zipfile as _zipfile
from pathlib import Path

import click

from .config import ScriptcastConfig, extract_config_prefix
from .export import AggNotFoundError, apply_scriptcast_watermark, generate_export
from .generator import build_config_from_sc_text, generate_from_sc
from .recorder import record as do_record

logger = logging.getLogger(__name__)


def _default_shell() -> str:
    return os.environ.get("SHELL", "bash")


def _resolve_theme(theme: str) -> Path:
    _BUILTIN_THEMES_DIR = Path(__file__).parent / "assets" / "themes"
    builtin = _BUILTIN_THEMES_DIR / f"{theme}.sh"
    theme_path = builtin if builtin.exists() else Path(theme)
    if not theme_path.exists():
        raise click.ClickException(f"Theme not found: {theme!r}")
    return theme_path


def build_config(
    script_path: Path | None,
    theme_path: Path | None,
    directive_prefix: str,
    trace_prefix: str,
    shell: str,
) -> ScriptcastConfig:
    """Build a fully resolved ScriptcastConfig before recording starts.

    Layer order: defaults → theme prefix → script prefix.
    Theme and script prefixes are concatenated into a single tmp .sh,
    recorded (fast — all no-ops/assignments), and fed into
    build_config_from_sc_text so shell variable expansion is handled
    correctly (e.g. : SC set prompt "${GREEN} > ${RESET}").

    For .sc inputs, also applies the .sc's pre-scene set directives on top.
    """
    base = ScriptcastConfig(
        directive_prefix=directive_prefix,
        trace_prefix=trace_prefix,
    )

    prefix_parts: list[str] = []
    if theme_path is not None:
        prefix_parts.append(extract_config_prefix(theme_path.read_text(), directive_prefix))
    if script_path is not None and script_path.suffix.lower() == ".sh":
        prefix_parts.append(extract_config_prefix(script_path.read_text(), directive_prefix))

    if prefix_parts:
        combined = "#!/bin/sh\n" + "\n".join(filter(None, prefix_parts))
        tmp_fd, tmp_sh_str = tempfile.mkstemp(suffix=".sh")
        os.close(tmp_fd)
        tmp_sh = Path(tmp_sh_str)
        tmp_sc = tmp_sh.with_suffix(".sc")
        try:
            tmp_sh.write_text(combined)
            tmp_sh.chmod(0o755)
            do_record(tmp_sh, tmp_sc, base, shell)
            if tmp_sc.exists():
                base = build_config_from_sc_text(tmp_sc.read_text())
                base.directive_prefix = directive_prefix
                base.trace_prefix = trace_prefix
        finally:
            tmp_sh.unlink(missing_ok=True)
            tmp_sc.unlink(missing_ok=True)

    if script_path is not None and script_path.suffix.lower() == ".sc":
        base = build_config_from_sc_text(script_path.read_text(), base=base)

    return base


class _ScriptOrSubcommandGroup(click.Group):
    """Click group that treats an unknown first positional as an input file path.

    Overrides ``parse_args`` so that when the first remaining token after
    option parsing is not a registered subcommand name, the group delegates to
    ``click.Command.parse_args`` instead of ``click.Group.parse_args``.  This
    leaves the token in ``ctx.args`` (never in ``ctx._protected_args``) and
    allows ``invoke_without_command=True`` to route straight to the callback.
    No private Click APIs are accessed.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Use click.Command.parse_args (grandparent) to parse options, which
        # puts remaining tokens into ctx.args without touching _protected_args.
        rest = click.Command.parse_args(self, ctx, args)
        if rest and rest[0] not in self.commands:
            # First remaining token is not a subcommand — treat it as an input
            # file path positional.  Keep everything in ctx.args so that
            # Group.invoke sees empty _protected_args and routes via
            # invoke_without_command to our callback.
            return rest
        # First remaining token IS a known subcommand (or there are no tokens).
        # Delegate to the standard Group.parse_args to set up routing correctly.
        # We reset ctx first since Command.parse_args already wrote to ctx.args.
        # ctx.params is already populated from the first pass above.
        # click.Group.parse_args calls Command.parse_args internally, but
        # Parameter.handle_parse_result skips keys already present in ctx.params,
        # so options are not double-applied. This holds as of Click 8.x.
        ctx.args = args
        return click.Group.parse_args(self, ctx, args)


@click.group(
    cls=_ScriptOrSubcommandGroup,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--no-export", is_flag=True, default=False,
              help="Stop after generating .cast file(s); do not export to image.")
@click.option("--theme", default=None,
              help="Visual theme: built-in name (e.g. 'aurora') or path to a .sh theme file.")
@click.option(
    "--format", "output_format",
    default="png",
    type=click.Choice(["gif", "png"]),
    show_default=True,
    help="Export format.",
)
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--shell", default=None)
@click.option("--split-scenes/--no-split-scenes", default=False)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--xtrace-log", is_flag=True, default=False,
              help="Save raw xtrace capture to <stem>.xtrace (only valid for .sh input).")
@click.pass_context
def cli(
    ctx: click.Context,
    output_dir: str | None,
    no_export: bool,
    theme: str | None,
    output_format: str,
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
    split_scenes: bool,
    verbose: bool,
    xtrace_log: bool,
) -> None:
    """Generate terminal demos from shell scripts, .sc files, or .cast files.

    The input file type determines the start stage:

    \b
      .sh   record → generate → export  (all stages)
      .sc            generate → export
      .cast                    export

    Use --no-export to stop after the generate stage (.sh and .sc only).

    Options must be placed before the input file path:

        scriptcast [OPTIONS] INPUT
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(name)s %(levelname)s %(message)s" if verbose else "%(message)s"
    logging.basicConfig(level=log_level, format=log_format)

    if ctx.invoked_subcommand is not None:
        return

    if not ctx.args:
        click.echo(ctx.get_help())
        return

    if len(ctx.args) > 1:
        raise click.UsageError(
            f"Unexpected arguments after input path: {ctx.args[1:]}. "
            "All options must be placed before the input path."
        )

    in_path = Path(ctx.args[0])
    if not in_path.exists():
        raise click.ClickException(f"File not found: {ctx.args[0]}")

    suffix = in_path.suffix.lower()
    if suffix not in (".sh", ".sc", ".cast"):
        raise click.UsageError(
            f"Unsupported file type '{suffix}'. Expected .sh, .sc, or .cast."
        )

    if no_export and suffix == ".cast":
        raise click.UsageError(
            "--no-export requires a .sh or .sc input (a .cast file is already at the export stage)."
        )

    if xtrace_log and suffix != ".sh":
        raise click.UsageError(
            "--xtrace-log requires a .sh input (xtrace is captured during recording)."
        )

    out_dir = Path(output_dir) if output_dir else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_shell = shell or _default_shell()
    theme_path = _resolve_theme(theme) if theme else None

    config = build_config(
        script_path=in_path if suffix != ".cast" else None,
        theme_path=theme_path,
        directive_prefix=directive_prefix,
        trace_prefix=trace_prefix,
        shell=resolved_shell,
    )
    logger.debug("Config: width=%d height=%d type_speed=%d prompt=%r", config.width, config.height, config.type_speed, config.prompt)

    # Stage 1: record (only for .sh input)
    sc_path: Path | None = None
    if suffix == ".sh":
        sc_path = out_dir / in_path.with_suffix(".sc").name
        logger.info("Recording %s ...", in_path.name)
        do_record(in_path, sc_path, config, resolved_shell, xtrace_log=xtrace_log)
    elif suffix == ".sc":
        sc_path = in_path

    # Stage 2: generate .cast(s)
    if suffix == ".cast":
        cast_paths = [in_path]
    else:
        logger.info("Generating .cast ...")
        cast_paths = generate_from_sc(
            sc_path,
            out_dir,
            output_stem=in_path.stem,
            split_scenes=split_scenes,
            base=config,
        )

    if no_export:
        for p in cast_paths:
            logger.info("Generated: %s", p)
        return

    # Stage 3: export
    logger.info("Exporting to %s ...", output_format.upper())
    for cast_path in cast_paths:
        _bar: list = [None]

        def on_frame(current: int, total: int) -> None:
            if _bar[0] is None:
                _bar[0] = click.progressbar(
                    length=total,
                    label=f"{output_format.upper()}   ",
                    width=0,
                    show_eta=True,
                    file=sys.stderr,
                )
                _bar[0].__enter__()
            _bar[0].update(1)

        try:
            export_path = generate_export(
                cast_path,
                config.theme if config.theme.frame else None,
                format=output_format,
                on_frame=on_frame,
            )
            if not config.theme.frame and config.theme.scriptcast_watermark:
                apply_scriptcast_watermark(export_path, config.theme)
        except (AggNotFoundError, RuntimeError) as e:
            raise click.ClickException(str(e))
        finally:
            if _bar[0] is not None:
                _bar[0].__exit__(None, None, None)
        logger.info("Generated: %s", export_path)


@cli.command()
@click.option(
    "--prefix",
    default=str(Path.home() / ".local" / "bin"),
    show_default=True,
    help="Installation directory for agg and fonts.",
)
def install(prefix: str) -> None:
    """Install the agg binary and JetBrains Mono fonts."""
    prefix_path = Path(prefix).expanduser()
    prefix_path.mkdir(parents=True, exist_ok=True)
    fonts_dir = prefix_path / "fonts"
    fonts_dir.mkdir(exist_ok=True)

    machine = platform.machine().lower()
    if sys.platform == "linux":
        if machine == "x86_64":
            agg_asset = "agg-x86_64-unknown-linux-gnu"
        elif machine in ("aarch64", "arm64"):
            agg_asset = "agg-aarch64-unknown-linux-gnu"
        else:
            raise click.ClickException(f"Unsupported Linux architecture: {machine}")
    elif sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            agg_asset = "agg-aarch64-apple-darwin"
        else:
            agg_asset = "agg-x86_64-apple-darwin"
    else:
        raise click.ClickException(f"Unsupported OS: {sys.platform}")

    agg_url = f"https://github.com/asciinema/agg/releases/latest/download/{agg_asset}"

    with urllib.request.urlopen(
        "https://api.github.com/repos/JetBrains/JetBrainsMono/releases/latest"
    ) as _resp:
        _release = json.loads(_resp.read())
    font_url = next(
        a["browser_download_url"]
        for a in _release["assets"]
        if a["name"].endswith(".zip") and "JetBrainsMono" in a["name"]
    )

    agg_bin = prefix_path / ".agg-real"
    click.echo("Downloading agg ...")
    urllib.request.urlretrieve(agg_url, agg_bin)
    agg_bin.chmod(0o755)

    agg_wrapper = prefix_path / "agg"
    agg_wrapper.write_text(
        '#!/bin/sh\n'
        'exec "$(dirname "$0")/.agg-real"'
        ' --font-dir "$(dirname "$0")/fonts"'
        ' --font-family "JetBrains Mono"'
        ' "$@"\n'
    )
    agg_wrapper.chmod(0o755)

    click.echo("Downloading JetBrains Mono fonts ...")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        zip_path = Path(tf.name)
    try:
        urllib.request.urlretrieve(font_url, zip_path)
        with _zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.startswith("fonts/ttf/") and name.endswith(".ttf"):
                    (fonts_dir / Path(name).name).write_bytes(zf.read(name))
    finally:
        zip_path.unlink(missing_ok=True)

    click.echo(f"Installed to {prefix_path}")
    if shutil.which("agg") is None:
        click.echo(f"Warning: {prefix_path} is not in PATH. Add it to use agg directly:", err=True)
        click.echo(f'  export PATH="{prefix_path}:$PATH"', err=True)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].startswith("--") and " " in sys.argv[1]:
        extra = shlex.split(sys.argv[1])
        sys.argv = [sys.argv[0]] + extra + sys.argv[2:]
    cli()
