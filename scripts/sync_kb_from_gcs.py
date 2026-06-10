#!/usr/bin/env python3
"""
Backend Admin CLI: Sync Knowledge Base from Google Cloud Storage

Command-line interface for backend admins to sync the Knowledge Base
from GCS without accessing the frontend.

Usage:
    python scripts/sync_kb_from_gcs.py            # safe sync (no deletes)
    python scripts/sync_kb_from_gcs.py --delete   # mirror sync (destructive)
    python scripts/sync_kb_from_gcs.py --help

Environment Variables:
    API_BASE_URL:         Base URL of the API (default: http://localhost:8000)
    POWER_USER_API_KEY:   Backend admin API key (alternative to --api-key)
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Shared session — Cloud Run auth header (if any) is injected once in main().
_session = requests.Session()

# Cloud Run environments expose FastAPI behind nginx at the /api prefix.
# Local dev speaks directly to FastAPI on port 8000 with no prefix.
_ENV_URLS: dict[str, str] = {
    "local": "http://localhost:8000",
    "dev": os.getenv("DEV_API_URL", "https://funding-paper-agent-dev-rlmgqbcnyq-as.a.run.app/api"),
    "uat": os.getenv("UAT_API_URL", "https://funding-paper-agent-rlmgqbcnyq-as.a.run.app/api"),
}


def _get_gcloud_identity_token() -> str | None:
    """Acquire a Cloud Run identity token via the gcloud CLI."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True, text=True, timeout=15,
        )
        token = result.stdout.strip()
        return token if result.returncode == 0 and token else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_api_base_url() -> str:
    """Get API base URL from environment or use default."""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


def check_status(api_key: str = None):
    """Check GCS configuration status."""
    api_base = get_api_base_url()

    console.print("\n[bold cyan]Checking GCS Status...[/bold cyan]")

    try:
        params = {}
        if api_key:
            params["api_key"] = api_key

        response = _session.get(
            f"{api_base}/admin/kb/gcs/status",
            params=params,
            timeout=10
        )

        if response.status_code == 403:
            console.print("[bold red]✗ Authentication failed[/bold red]")
            console.print("Invalid API key. Check your POWER_USER_API_KEY.")
            return False

        response.raise_for_status()
        data = response.json()

        if data.get("configured") and data.get("accessible"):
            console.print(f"[bold green]✓ GCS Status: Configured & Accessible[/bold green]")
            console.print(f"  Bucket: {data.get('bucket_name')}")
            console.print(f"  Files: {data.get('files_count', 0)}")
        elif data.get("configured"):
            console.print(f"[bold yellow]⚠ GCS Status: Configured but Not Accessible[/bold yellow]")
            console.print(f"  Error: {data.get('error', 'Unknown error')}")
        else:
            console.print("[bold red]✗ GCS Status: Not Configured[/bold red]")
            console.print(data.get("message", ""))
            return False

        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]✗ Error connecting to API:[/bold red] {str(e)}")
        return False


def list_files(api_key: str = None):
    """List all files in GCS bucket."""
    api_base = get_api_base_url()

    console.print("\n[bold cyan]Listing GCS Files...[/bold cyan]")

    try:
        json_data = {}
        if api_key:
            json_data["api_key"] = api_key

        response = _session.post(
            f"{api_base}/admin/kb/gcs/list",
            json=json_data,
            timeout=30
        )

        if response.status_code == 403:
            console.print("[bold red]✗ Authentication failed[/bold red]")
            return

        response.raise_for_status()
        data = response.json()

        # Create table
        table = Table(title="GCS Knowledge Base Files", box=box.ROUNDED)
        table.add_column("Filename", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Size", style="green")
        table.add_column("Updated", style="yellow")

        for file in data.get("files", []):
            size_kb = file["size_bytes"] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            updated = file.get("updated", "")[:10] if file.get("updated") else "N/A"

            table.add_row(
                file["filename"],
                file["doc_type"],
                size_str,
                updated
            )

        console.print(table)
        console.print(f"\n[bold]Total:[/bold] {data['total']} files")
        console.print(f"[bold]Guidelines:[/bold] {data['guidelines_count']}")
        console.print(f"[bold]Past Papers:[/bold] {data['past_papers_count']}")

    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")


def sync_kb(api_key: str = None, confirm: bool = False):
    """Sync Knowledge Base from GCS.

    When ``confirm`` is True, deletions in GCS are mirrored locally
    (files removed from disk, embeddings pruned, tag entries cleaned).
    """
    api_base = get_api_base_url()

    mode_label = "MIRROR (destructive)" if confirm else "download-only"

    if confirm:
        console.print(Panel.fit(
            "[bold red]⚠ MIRROR mode[/bold red] — files removed from GCS will be "
            "deleted locally,\nincluding ChromaDB embeddings and KB tag mappings.",
            border_style="red",
        ))

    console.print(f"\n[bold cyan]Syncing Knowledge Base from GCS — mode: {mode_label}[/bold cyan]")
    console.print("This may take a minute...\n")

    started = time.monotonic()

    try:
        json_data = {"confirm": confirm}
        if api_key:
            json_data["api_key"] = api_key

        response = _session.post(
            f"{api_base}/admin/kb/gcs/sync",
            json=json_data,
            timeout=300  # 5 minute timeout for large syncs
        )

        if response.status_code == 403:
            console.print("[bold red]✗ Authentication failed[/bold red]")
            return

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            console.print("[bold red]✗ Sync failed[/bold red]")
            return

        elapsed = time.monotonic() - started
        _render_sync_summary(data, mode_label=mode_label, mirror=confirm, elapsed=elapsed)

    except requests.exceptions.Timeout:
        console.print("[bold red]✗ Request timeout[/bold red]")
        console.print("Sync is taking longer than expected. Check server logs.")
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")


def _render_sync_summary(data: dict, mode_label: str, mirror: bool, elapsed: float):
    """Render the post-sync summary panel + file lists + footer.

    The API returns a flat ``synced`` count per category; it does not split
    ``added`` vs ``updated`` and does not report ``skipped``. We surface what
    the API gives us honestly: synced is labelled "added or updated", and
    skipped is omitted rather than fabricated.
    """
    synced = data.get("synced", {"guidelines": 0, "past_papers": 0})
    removed = data.get("removed", {"guidelines": [], "past_papers": []})
    errors = data.get("errors", []) or []
    removed_count = len(removed.get("guidelines", [])) + len(removed.get("past_papers", []))

    summary_table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    summary_table.add_column("Field", style="bold")
    summary_table.add_column("Value")
    summary_table.add_row("Mode", mode_label)
    summary_table.add_row(
        "Synced (added or updated)",
        f"{data.get('total_synced', synced.get('guidelines', 0) + synced.get('past_papers', 0))} "
        f"(guidelines: {synced.get('guidelines', 0)}, past_papers: {synced.get('past_papers', 0)})",
    )
    if mirror:
        summary_table.add_row(
            "Removed",
            f"{removed_count} (guidelines: {len(removed.get('guidelines', []))}, "
            f"past_papers: {len(removed.get('past_papers', []))})",
        )
    else:
        summary_table.add_row("Removed", "0 (download-only mode)")
    summary_table.add_row(
        "Errors",
        f"[bold yellow]{len(errors)}[/bold yellow]" if errors else "0",
    )

    console.print(Panel.fit(
        summary_table,
        title="[bold green]✓ Sync Completed[/bold green]",
        border_style="green",
    ))

    if removed_count:
        console.print("\n[bold]Removed files:[/bold]")
        for fname in removed.get("guidelines", []):
            console.print(f"  - guidelines/{fname}")
        for fname in removed.get("past_papers", []):
            console.print(f"  - past_papers/{fname}")

    if errors:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for error in errors:
            console.print(f"  - {error}")

    console.print(
        f"\n[dim]Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"in {elapsed:.1f}s[/dim]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Backend Admin CLI for GCS Knowledge Base management.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Safe sync against local backend (default)
  export POWER_USER_API_KEY=YOUR_KEY
  python scripts/sync_kb_from_gcs.py

  # Safe sync against DEV or UAT Cloud Run
  python scripts/sync_kb_from_gcs.py --env dev
  python scripts/sync_kb_from_gcs.py --env uat

  # Mirror sync — DESTRUCTIVE: removes local files no longer in GCS,
  # along with their ChromaDB embeddings and tag mappings
  python scripts/sync_kb_from_gcs.py --delete
  python scripts/sync_kb_from_gcs.py --env uat --delete

  # Check GCS configuration / connectivity
  python scripts/sync_kb_from_gcs.py --action status
  python scripts/sync_kb_from_gcs.py --env dev --action status

  # List all files currently in the GCS bucket
  python scripts/sync_kb_from_gcs.py --action list

  # Override with an explicit URL (takes precedence over --env)
  python scripts/sync_kb_from_gcs.py --api-url https://my-custom-url.run.app
        """
    )

    parser.add_argument(
        "--api-key",
        help="Backend admin API key. Defaults to the POWER_USER_API_KEY env var.",
        default=os.getenv("POWER_USER_API_KEY")
    )

    parser.add_argument(
        "--action",
        choices=["status", "list", "sync"],
        default="sync",
        help="Action to perform: 'sync' (default), 'status' (check GCS config), or 'list' (list bucket files).",
    )

    parser.add_argument(
        "--env",
        choices=["local", "dev", "uat"],
        default="local",
        help="Target environment: 'local' (default, localhost:8000), 'dev' (DEV Cloud Run), 'uat' (UAT Cloud Run).",
    )

    parser.add_argument(
        "--api-url",
        help="Explicit API base URL. Overrides --env when both are provided.",
        default=None
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="DESTRUCTIVE. Mirror GCS deletions: remove local files, ChromaDB embeddings, and tag mappings for files no longer in GCS.",
    )

    args = parser.parse_args()

    # API key is optional — backend may run unauthenticated in dev.
    if not args.api_key:
        console.print("[bold yellow]Note:[/bold yellow] No API key provided.")
        console.print("If POWER_USER_API_KEY is set in the backend .env, authentication will fail.")
        console.print("If not set, proceeding without authentication...\n")

    # Resolve target URL: explicit --api-url wins; otherwise use --env mapping.
    if args.api_url:
        os.environ["API_BASE_URL"] = args.api_url
    elif args.env != "local":
        os.environ["API_BASE_URL"] = _ENV_URLS[args.env]

    # Cloud Run environments (dev/uat) block unauthenticated requests via IAM.
    # Auto-fetch an identity token via gcloud and inject it as a Bearer header.
    if args.env in ("dev", "uat"):
        token = _get_gcloud_identity_token()
        if token:
            _session.headers.update({"Authorization": f"Bearer {token}"})
            console.print("[dim]Cloud Run auth: identity token acquired via gcloud.[/dim]")
        else:
            console.print(
                "[bold yellow]Warning:[/bold yellow] Could not obtain a gcloud identity token. "
                "Cloud Run IAM will likely reject the request.\n"
                "Fix: run [bold]gcloud auth login[/bold] then retry."
            )

    # Print header
    env_label = args.env.upper() if not args.api_url else "custom"
    console.print(f"\n[bold]Backend Admin: GCS KB Management ({env_label})[/bold]")
    console.print(f"API: {get_api_base_url()}\n")

    # Execute action
    if args.action == "status":
        check_status(args.api_key)
    elif args.action == "list":
        list_files(args.api_key)
    elif args.action == "sync":
        # Always check status first
        if check_status(args.api_key):
            sync_kb(args.api_key, confirm=args.delete)

    console.print()


if __name__ == "__main__":
    # Check if rich is installed
    try:
        import rich
    except ImportError:
        print("Error: 'rich' package is required for this script")
        print("Install it with: pip install rich")
        sys.exit(1)

    main()
