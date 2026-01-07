from __future__ import annotations

from pathlib import Path

import click

from models.database import initialize_db
from models.job import list_jobs as list_jobs_model
from services.scraper_service import ScraperService
from utils.config import load_searches, load_settings


def _default_settings_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "settings.yaml"


def _default_searches_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "searches.yaml"


@click.group()
@click.option(
    "--settings",
    "settings_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_settings_path(),
    show_default=True,
    help="Path to settings.yaml.",
)
@click.option(
    "--searches",
    "searches_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_searches_path(),
    show_default=True,
    help="Path to searches.yaml.",
)
@click.pass_context
def cli(ctx: click.Context, settings_path: Path, searches_path: Path) -> None:
    """Job tracker CLI."""
    ctx.ensure_object(dict)
    ctx.obj["settings_path"] = settings_path
    ctx.obj["searches_path"] = searches_path


@cli.command()
@click.option("--search", "search_name", type=str, default=None)
@click.pass_context
def scrape(ctx: click.Context, search_name: str | None) -> None:
    """Run configured searches and store results."""
    searches = load_searches(ctx.obj["searches_path"])
    settings = load_settings(ctx.obj["settings_path"])
    db_path = settings.get("database", {}).get("path")
    if not db_path:
        raise click.ClickException("Database path missing from settings.yaml")
    service = ScraperService(db_path, searches)
    results = service.run(search_name=search_name)
    click.echo(f"Scraped {len(results)} jobs")


@cli.command("init-db")
@click.pass_context
def init_db(ctx: click.Context) -> None:
    """Initialize the SQLite database schema."""
    settings = load_settings(ctx.obj["settings_path"])
    db_path = settings.get("database", {}).get("path")
    if not db_path:
        raise click.ClickException("Database path missing from settings.yaml")
    conn = initialize_db(db_path)
    conn.close()
    click.echo(f"Initialized database at {db_path}")


@cli.group()
def jobs() -> None:
    """Job listing commands."""


@jobs.command("list")
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("--since-iso", type=str, default=None)
@click.pass_context
def list_jobs(ctx: click.Context, limit: int, since_iso: str | None) -> None:
    settings = load_settings(ctx.obj["settings_path"])
    db_path = settings.get("database", {}).get("path")
    if not db_path:
        raise click.ClickException("Database path missing from settings.yaml")
    conn = initialize_db(db_path)
    jobs = list_jobs_model(conn, limit=limit, since_iso=since_iso)
    conn.close()
    if not jobs:
        click.echo("No jobs found")
        return
    for job in jobs:
        click.echo(f"{job.id}\t{job.company}\t{job.title}\t{job.location}")


if __name__ == "__main__":
    cli()
