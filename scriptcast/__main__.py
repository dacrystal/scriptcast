# scriptcast/__main__.py
from __future__ import annotations

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

from .config import ScriptcastConfig
from .export import AggNotFoundError, apply_scriptcast_watermark, generate_export
from .generator import generate_from_sc
from .recorder import record as do_record


def _default_shell() -> str:
    return os.environ.get("SHELL", "bash")


def _make_config(
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
) -> tuple[ScriptcastConfig, str]:
    config = ScriptcastConfig(
        directive_prefix=directive_prefix,
        trace_prefix=trace_prefix,
    )
    resolved_shell = shell or _default_shell()
    return config, resolved_shell


class _ScriptOrSubcommandGroup(click.Group):
    """Click group that treats an unknown first positional as a script path.

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
            # First remaining token is not a subcommand — treat it as a script
            # path positional.  Keep everything in ctx.args so that
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
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--shell", default=None)
@click.option("--split-scenes/--no-split-scenes", default=False)
@click.pass_context
def cli(
    ctx: click.Context,
    output_dir: str | None,
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
    split_scenes: bool,
) -> None:
    """Generate terminal demos from shell scripts.

    Options must be placed before the script path:

        scriptcast [OPTIONS] SCRIPT
    """
    if ctx.invoked_subcommand is not None:
        return

    if not ctx.args:
        click.echo(ctx.get_help())
        return

    script_path = Path(ctx.args[0])
    if len(ctx.args) > 1:
        raise click.UsageError(
            f"Unexpected arguments after script path: {ctx.args[1:]}. "
            "All options must be placed before the script path."
        )
    if not script_path.exists():
        raise click.ClickException(f"Script not found: {ctx.args[0]}")

    out_dir = Path(output_dir) if output_dir else script_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell)
    sc_path = out_dir / script_path.with_suffix(".sc").name
    do_record(script_path, sc_path, config, resolved_shell)
    generate_from_sc(
        sc_path, out_dir,
        output_stem=script_path.stem,
        split_scenes=split_scenes,
    )


@cli.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--shell", default=None)
def record(
    script: str,
    output_dir: str | None,
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
) -> None:
    """Stage 1: run script and write .sc file."""
    script_path = Path(script)
    out_dir = Path(output_dir) if output_dir else script_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell)
    sc_path = out_dir / script_path.with_suffix(".sc").name
    do_record(script_path, sc_path, config, resolved_shell)
    click.echo(f"Recorded: {sc_path}")


@cli.command()
@click.argument("sc_file", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--split-scenes/--no-split-scenes", default=False)
def generate(sc_file: str, output_dir: str | None, split_scenes: bool) -> None:
    """Stage 2: read .sc and write .cast file(s)."""
    sc_path = Path(sc_file)
    out_dir = Path(output_dir) if output_dir else sc_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = generate_from_sc(sc_path, out_dir, split_scenes=split_scenes)
    for p in paths:
        click.echo(f"Generated: {p}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--theme", default=None,
              help="Visual theme: built-in name (e.g. 'dark') or path to a .sh theme file.")
@click.option(
    "--format", "output_format",
    default="gif",
    type=click.Choice(["gif", "apng"]),
    show_default=True,
    help="Output format.",
)
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--shell", default=None)
def export(
    input_file: str,
    output_dir: str | None,
    theme: str | None,
    output_format: str,
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
) -> None:
    """Generate GIFs or APNGs from .sc, .cast, or .sh files."""
    from .config import FrameConfig, ScriptcastConfig
    from .theme import apply_theme_to_configs, load_theme, scan_sc_for_theme

    in_path = Path(input_file)
    suffix = in_path.suffix.lower()
    out_dir = Path(output_dir) if output_dir else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if suffix not in (".sc", ".cast", ".sh"):
        raise click.UsageError(
            f"Unsupported file type '{suffix}'. Expected .sc, .cast, or .sh."
        )

    frame_config = FrameConfig()

    # For .sh: record first to produce a .sc file
    sc_path: Path | None = None
    if suffix == ".sh":
        config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell)
        sc_path = out_dir / in_path.with_suffix(".sc").name
        do_record(in_path, sc_path, config, resolved_shell)
    elif suffix == ".sc":
        sc_path = in_path

    # Theme loading from .sc (not applicable for .cast)
    if sc_path is not None and sc_path.exists():
        sc_theme = scan_sc_for_theme(sc_path)
        if sc_theme:
            dummy_sc = ScriptcastConfig()  # theme recorder-config fields are unused in export
            apply_theme_to_configs(sc_theme, frame_config, dummy_sc)

    if theme:
        dummy_sc = ScriptcastConfig()  # theme recorder-config fields are unused in export
        try:
            theme_dict = load_theme(theme)
        except FileNotFoundError as e:
            raise click.ClickException(str(e))
        apply_theme_to_configs(theme_dict, frame_config, dummy_sc)

    # Resolve cast file list
    if suffix == ".cast":
        cast_paths = [in_path]
    else:
        cast_paths = generate_from_sc(sc_path, out_dir, split_scenes=True)

    for cast_path in cast_paths:
        try:
            export_path = generate_export(
                cast_path,
                frame_config if frame_config.frame else None,
                format=output_format,
            )
            if not frame_config.frame and frame_config.scriptcast_watermark:
                apply_scriptcast_watermark(export_path, frame_config)
        except (AggNotFoundError, RuntimeError) as e:
            raise click.ClickException(str(e))
        click.echo(f"Generated: {export_path}")


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

    import json as _json
    with urllib.request.urlopen(
        "https://api.github.com/repos/JetBrains/JetBrainsMono/releases/latest"
    ) as _resp:
        _release = _json.loads(_resp.read())
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
