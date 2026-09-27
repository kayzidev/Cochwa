"""Interface CLI du même cœur applicatif que la GUI."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import requests

from romget import __version__
from romget.api.redump import get_datfile
from romget.config import Config
from romget.services.conversion import convert_chd
from romget.services.index import LibraryIndex
from romget.services.jobs import DownloadManager, JobStore
from romget.services.library import launch, scan, verify_manifest
from romget.services.search import SearchService
from romget.steam import trigger_srm_reparse
from romget.util import human_size


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Valeur positive requise")
    return number


def build_parser():
    parser = argparse.ArgumentParser(
        prog="romget", description="Bibliothèque PS2 — recherche, transferts vérifiés et PCSX2"
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, help="Fichier TOML explicite")
    parser.add_argument("--json", action="store_true", help="Sortie structurée sur stdout")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Recherche PS2 multi-sources")
    search.add_argument("query")
    search.add_argument("--source", choices=["all", "ia_redump", "minerva"], default="all")
    search.add_argument("--limit", type=positive, default=20)
    search.add_argument("--page", type=positive, default=1)
    search.add_argument(
        "--verified-only", action="store_true", help="Items contenant un hash source reconnu Redump"
    )
    search.add_argument("--region", default="")
    search.add_argument("--language", default="")
    sub.add_parser("inspect", help="Afficher les fichiers et éditions d’un item").add_argument(
        "identifier"
    )
    listing = sub.add_parser("list", help="Bibliothèque locale")
    listing.add_argument("--query", default="")
    dl = sub.add_parser("download", help="Sélection explicite puis téléchargement")
    dl.add_argument("identifier")
    dl.add_argument("--file", action="append", default=[], help="Nom exact ; option répétable")
    dl.add_argument(
        "--all", action="store_true", help="Tous les fichiers de cet item, y compris variantes"
    )
    dl.add_argument("--dry-run", action="store_true")
    dl.add_argument("--enqueue", action="store_true")
    dl.add_argument("--chd", action="store_true")
    dl.add_argument("--media", choices=["cd", "dvd"])
    dl.add_argument("--add-steam", action="store_true")
    convert = sub.add_parser("convert", help="Convertir un disque et conserver les sources")
    convert.add_argument("source", type=Path)
    convert.add_argument("--media", choices=["cd", "dvd"])
    verify = sub.add_parser("verify", help="Vérifier un manifeste ou identifier une image importée")
    verify.add_argument("path", type=Path)
    play = sub.add_parser("play", help="Lancer une image explicite")
    play.add_argument("path", type=Path)
    sub.add_parser("doctor", help="Diagnostic local sans réseau")
    sub.add_parser("add-steam", help="Ouvrir SRM ; ajout manuel dans SRM")
    providers = sub.add_parser("providers", help="État du provider ou actualisation Redump")
    providers.add_argument("sub", choices=["list", "refresh"], nargs="?", default="list")
    providers.add_argument("--force", action="store_true")
    jobs = sub.add_parser("jobs", help="File persistante")
    jobs.add_argument(
        "action", choices=["list", "run", "resume", "cancel"], default="list", nargs="?"
    )
    jobs.add_argument("id", nargs="?")
    return parser


def emit(data, args):
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def run_jobs(store, job_id=None, progress=None):
    errors = []
    manager = DownloadManager(
        store, lambda kind, msg: errors.append(msg) if kind == "error" else None
    )
    manager.start()
    last_progress = 0
    try:
        while True:
            rows = store.list()
            selected = [r for r in rows if job_id is None or r["id"] == job_id]
            if progress and time.monotonic() - last_progress > 1:
                progress(selected)
                last_progress = time.monotonic()
            if selected and all(r["status"] not in {"queued", "running"} for r in selected):
                return selected
            if not selected:
                return []
            if errors:
                raise RuntimeError(errors[0])
            time.sleep(0.2)
    except KeyboardInterrupt:
        manager.close()
        if manager._thread:
            manager._thread.join(timeout=35)
        raise
    finally:
        manager.close()
        if manager._thread:
            manager._thread.join(timeout=35)


def report_progress(rows):
    for row in rows:
        if row["status"] in {"running", "queued"}:
            print(
                f"{row['title']} : {human_size(row['progress'])} / {human_size(row['total'])} ({row['status']})",
                file=sys.stderr,
            )


def doctor(config):
    import importlib.util

    root = config.ps2_dir
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "rom_directory": str(root),
        "rom_directory_exists": root.is_dir(),
        "free_bytes": shutil.disk_usage(root).free if root.is_dir() else None,
        "launcher": str(config.launcher),
        "launcher_exists": config.launcher.is_file(),
        "chdman": shutil.which("chdman"),
        "flatpak": shutil.which("flatpak"),
        "tkinter": bool(importlib.util.find_spec("tkinter")),
        "pillow": bool(importlib.util.find_spec("PIL")),
        "artwork_key_configured": bool(config.steamgrid_api_key),
        "cache": str(config.cache_dir),
        "redump_cache_exists": (config.cache_dir / "ps2_datfile.json").is_file(),
        "state": str(config.state_dir),
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stderr)
    try:
        cfg = Config.load(args.config)
        search = SearchService(cfg)
        command = args.command
        if command == "search":
            result = search.search(
                args.query,
                source=args.source,
                page=args.page,
                limit=args.limit,
                verified_only=args.verified_only,
                region=args.region,
                language=args.language,
            )
            if args.json:
                emit(
                    {
                        "games": [g.to_dict() for g in result.games],
                        "total_items": result.total_items,
                        "page": result.page,
                        "has_more": result.has_more,
                        "source_totals": result.source_totals,
                        "warnings": result.warnings,
                        "suggestions": result.suggestions,
                    },
                    args,
                )
            else:
                print(
                    f"Page {result.page} — {len(result.games)} items affichés / {result.total_items} items source"
                )
                for g in result.games:
                    print(
                        f"{g.identifier}\n  {g.clean_title} — {human_size(g.total_size)} — {g.label}"
                    )
                    if g.external:
                        print("  " + g.source_reference()["url"])
                if result.suggestions:
                    print("Suggestions : " + " / ".join(result.suggestions))
                for warning in result.warnings:
                    print(warning, file=sys.stderr)
        elif command == "inspect":
            emit(search.item(args.identifier).to_dict(), args)
        elif command == "list":
            games = [
                g
                for g in scan(cfg.ps2_dir, LibraryIndex(cfg.state_dir / "library.sqlite3"))
                if args.query.casefold() in g.title.casefold()
            ]
            if args.json:
                emit([g.to_dict() for g in games], args)
            else:
                for g in games:
                    print(
                        f"{g.title}\n  {human_size(g.size)} — {g.status}\n  "
                        + ", ".join(str(p) for p in g.paths)
                    )
                print(f"{len(games)} jeu(x)")
        elif command == "doctor":
            emit(doctor(cfg), args)
        elif command == "convert":
            emit(str(convert_chd(args.source, args.media)), args)
        elif command == "verify":
            if args.path.is_dir():
                results = verify_manifest(args.path)
                emit(results, args)
                if not all(r["ok"] for r in results):
                    return 1
            else:
                result = LibraryIndex(cfg.state_dir / "library.sqlite3").verify(
                    args.path, get_datfile(cfg.cache_dir, cfg.datfile_url)
                )
                emit(result, args)
        elif command == "play":
            process, log = launch(args.path, cfg)
            emit({"pid": process.pid, "log": str(log), "status": "started"}, args)
        elif command == "add-steam":
            from contextlib import redirect_stdout

            with redirect_stdout(sys.stderr):
                ok = trigger_srm_reparse(cfg.srm_flatpak)
            emit({"srm_opened": ok, "steam_saved": False}, args)
            if not ok:
                return 1
        elif command == "providers":
            if args.sub == "refresh":
                index = get_datfile(cfg.cache_dir, cfg.datfile_url)
                if args.force:
                    index.load(force=True)
                emit({"hashes": len(index.md5_to_title), "status": index.status}, args)
                if not index._loaded:
                    return 1
            else:
                emit(
                    {
                        name: {
                            "enabled": provider.enabled,
                            "mode": "external-torrent" if name == "minerva" else "on-demand",
                        }
                        for name, provider in cfg.providers.items()
                        if name in {"ia_redump", "minerva"}
                    },
                    args,
                )
        elif command == "jobs":
            store = JobStore(cfg.state_dir)
            if args.action in {"resume", "cancel"}:
                if not args.id:
                    raise ValueError("Identifiant de tâche requis")
                if args.action == "resume":
                    store.resume(args.id)
                else:
                    rows = {r["id"]: r for r in store.list()}
                    if args.id not in rows:
                        raise ValueError("Tâche inconnue")
                    if rows[args.id]["status"] == "running":
                        raise ValueError(
                            "Annuler la tâche active depuis l’interface qui la possède"
                        )
                    store.update(args.id, status="cancelled")
            rows = (
                run_jobs(store, progress=None if args.json else report_progress)
                if args.action == "run"
                else store.list()
            )
            emit([{k: v for k, v in row.items() if k != "payload"} for row in rows], args)
            if args.action == "run" and any(r["status"] == "failed" for r in rows):
                return 1
        elif command == "download":
            if args.enqueue and (args.chd or args.add_steam):
                raise ValueError("--enqueue ne combine pas conversion ou ouverture SRM")
            game = search.item(args.identifier)
            names = [f["name"] for f in game.files] if args.all else args.file
            if not names:
                raise ValueError("Choisir --file NOM (répétable), ou --all après romget inspect")
            selected = [f for f in game.files if f["name"] in names]
            if len(set(names)) != len(selected):
                raise ValueError("Fichier absent des métadonnées")
            if (
                args.chd
                and any(f["name"].lower().endswith(".iso") for f in selected)
                and not args.media
            ):
                raise ValueError("--chd sur ISO exige --media cd ou dvd")
            if args.dry_run:
                emit(
                    {
                        "identifier": game.identifier,
                        "files": selected,
                        "total_size": sum(f["size"] for f in selected),
                        "destination_root": str(cfg.download_path),
                    },
                    args,
                )
                return 0
            store = JobStore(cfg.state_dir)
            job_id = store.add(game, names, cfg.download_path)
            if args.enqueue:
                emit({"job_id": job_id, "status": "queued"}, args)
                return 0
            rows = run_jobs(store, job_id, None if args.json else report_progress)
            row = rows[0]
            if row["status"] != "completed":
                raise RuntimeError(row["error"] or row["status"])
            payload = json.loads(row["payload"])
            destination = Path(payload["destination"])
            if args.chd:
                for item in selected:
                    if Path(item["name"]).suffix.lower() in {".iso", ".cue"}:
                        convert_chd(destination / item["name"], args.media)
            if args.add_steam:
                from contextlib import redirect_stdout

                with redirect_stdout(sys.stderr):
                    ok = trigger_srm_reparse(cfg.srm_flatpak)
                if not ok:
                    raise RuntimeError("Téléchargé ; ouverture SRM échouée")
            emit({"job_id": job_id, "status": "completed", "destination": str(destination)}, args)
        return 0
    except KeyboardInterrupt:
        print("Interrompu ; fragments conservés pour reprise.", file=sys.stderr)
        return 130
    except (ValueError, OSError, RuntimeError, requests.RequestException) as exc:
        if args.json:
            print(
                json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False),
                file=sys.stderr,
            )
        else:
            print(f"Erreur : {exc}", file=sys.stderr)
        return 2 if isinstance(exc, ValueError) else 1


if __name__ == "__main__":
    raise SystemExit(main())
