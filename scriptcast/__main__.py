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


class ScriptOrSubcommandGroup(click.Group):
    """A Click group that treats an unknown first argument as a script path."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        result = super().parse_args(ctx, args)
        if ctx._protected_args and ctx._protected_args[0] not in self.commands:
            ctx.args = ctx._protected_args + ctx.args
            ctx._protected_args = []
        return result


@click.group(
    cls=ScriptOrSubcommandGroup,
    invoke_without_command=True,
)
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--title/--no-title", default=False)
@click.option("--shell", default=None)
@click.option("--split-scenes/--no-split-scenes", default=False)
@click.pass_context
def cli(ctx, output_dir, directive_prefix, trace_prefix, title, shell, split_scenes):
    """Generate terminal demos from shell scripts."""
    if ctx.invoked_subcommand is not None:
        return

    if not ctx.args:
        click.echo(ctx.get_help())
        return

    remaining = list(ctx.args)
    script_str = None
    idx = 0
    while idx < len(remaining):
        arg = remaining[idx]
        if arg == "--output-dir" and idx + 1 < len(remaining):
            output_dir = remaining[idx + 1]
            idx += 2
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
            idx += 1
        elif arg == "--split-scenes":
            split_scenes = True
            idx += 1
        elif arg == "--no-split-scenes":
            split_scenes = False
            idx += 1
        elif not arg.startswith("-") and script_str is None:
            script_str = arg
            idx += 1
        else:
            idx += 1

    if script_str is None:
        click.echo(ctx.get_help())
        return

    script_path = Path(script_str)
    if not script_path.exists():
        raise click.ClickException(f"Script not found: {script_str}")

    out_dir = Path(output_dir) if output_dir else script_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    config, resolved_shell = _make_config(directive_prefix, trace_prefix, shell, title)
    sc_path = out_dir / script_path.with_suffix(".sc").name
    do_record(script_path, sc_path, config, resolved_shell)
    generate_from_sc(sc_path, out_dir, output_stem=script_path.stem, show_title=title, split_scenes=split_scenes)


@cli.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--directive-prefix", default="SC", show_default=True)
@click.option("--trace-prefix", default="+", show_default=True)
@click.option("--shell", default=None)
def record(script, output_dir, directive_prefix, trace_prefix, shell):
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
def generate(sc_file, output_dir, title, split_scenes):
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
def gif(sc_file, output_dir):
    """Generate GIFs from .cast files using agg."""
    sc_path = Path(sc_file)
    out_dir = Path(output_dir) if output_dir else sc_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = generate_from_sc(sc_path, out_dir, split_scenes=True)
    for cast_path in paths:
        try:
            gif_path = generate_gif(cast_path)
            click.echo(f"Generated: {gif_path}")
        except AggNotFoundError as e:
            raise click.ClickException(str(e))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].startswith("--") and " " in sys.argv[1]:
        extra = shlex.split(sys.argv[1])
        sys.argv = [sys.argv[0]] + extra + sys.argv[2:]
    cli()
