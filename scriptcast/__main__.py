# scriptcast/__main__.py
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

import click

from .config import ScriptcastConfig
from .generator import generate_from_sc
from .gif import AggNotFoundError, generate_gif
from .recorder import record as do_record


def _default_shell() -> str:
    return os.environ.get("SHELL", "bash")


def _make_config(
    directive_prefix: str,
    trace_prefix: str,
    shell: str | None,
    title: bool,
) -> tuple[ScriptcastConfig, str]:
    config = ScriptcastConfig(
        directive_prefix=directive_prefix,
        trace_prefix=trace_prefix,
        show_title=title,
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
@click.option("--title/--no-title", default=False)
@click.option("--shell", default=None)
@click.option("--split-scenes/--no-split-scenes", default=False)
@click.pass_context
def cli(
    ctx: click.Context,
    output_dir: str | None,
    directive_prefix: str,
    trace_prefix: str,
    title: bool,
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

    config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell, title)
    sc_path = out_dir / script_path.with_suffix(".sc").name
    do_record(script_path, sc_path, config, resolved_shell)
    generate_from_sc(
        sc_path, out_dir,
        output_stem=script_path.stem,
        show_title=title,
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
    config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell, False)
    sc_path = out_dir / script_path.with_suffix(".sc").name
    do_record(script_path, sc_path, config, resolved_shell)
    click.echo(f"Recorded: {sc_path}")


@cli.command()
@click.argument("sc_file", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--title/--no-title", default=False)
@click.option("--split-scenes/--no-split-scenes", default=False)
def generate(sc_file: str, output_dir: str | None, title: bool, split_scenes: bool) -> None:
    """Stage 2: read .sc and write .cast file(s)."""
    sc_path = Path(sc_file)
    out_dir = Path(output_dir) if output_dir else sc_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = generate_from_sc(sc_path, out_dir, show_title=title, split_scenes=split_scenes)
    for p in paths:
        click.echo(f"Generated: {p}")


@cli.command()
@click.argument("sc_file", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--frame/--no-frame", default=False, help="Add macOS window frame decoration.")
@click.option("--title", default="", show_default=False, help="Window title text.")
@click.option("--background", default=None, help="Background color: '#hex' or '#hex1,#hex2' gradient.")  # noqa: E501
@click.option("--margin", default=None, type=int, help="Outer margin in pixels (default: 82 when --background set).")  # noqa: E501
@click.option("--padding", default=None, type=int, help="Inner padding in pixels (default: 14).")
@click.option("--radius", default=12, show_default=True, type=int, help="Window corner radius.")
@click.option("--shadow/--no-shadow", default=True, help="Drop shadow behind window; only applies with --frame.")  # noqa: E501
@click.option("--shadow-color", default="#0000004d", show_default=True, help="Shadow color (RGBA hex).")  # noqa: E501
@click.option("--watermark", default=None, help="Watermark text (opt-in).")
@click.option("--watermark-color", default="#ffffff", show_default=True, help="Watermark color.")
def gif(
    sc_file: str,
    output_dir: str | None,
    frame: bool,
    title: str,
    background: str | None,
    margin: int | None,
    padding: int | None,
    radius: int,
    shadow: bool,
    shadow_color: str,
    watermark: str | None,
    watermark_color: str,
) -> None:
    """Generate GIFs from .cast files using agg."""
    from .config import FrameConfig

    sc_path = Path(sc_file)
    out_dir = Path(output_dir) if output_dir else sc_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = generate_from_sc(sc_path, out_dir, split_scenes=True)

    frame_config: FrameConfig | None = None
    if frame:
        frame_config = FrameConfig(
            title=title,
            background=background,
            margin_x=margin,
            margin_y=margin,
            padding_x=padding if padding is not None else 14,
            padding_y=padding if padding is not None else 14,
            radius=radius,
            shadow=shadow,
            shadow_color=shadow_color,
            watermark=watermark,
            watermark_color=watermark_color,
        )

    for cast_path in paths:
        try:
            gif_path = generate_gif(cast_path, frame_config)
        except (AggNotFoundError, RuntimeError) as e:
            raise click.ClickException(str(e))
        click.echo(f"Generated: {gif_path}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].startswith("--") and " " in sys.argv[1]:
        extra = shlex.split(sys.argv[1])
        sys.argv = [sys.argv[0]] + extra + sys.argv[2:]
    cli()
