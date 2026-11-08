"""yt2sp CLI – entry point semua perintah."""
from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm

from yt2sp.config import load_config
from yt2sp.store import db as database

app = typer.Typer(
    name="yt2sp",
    help="Pindah playlist YouTube Music ke Spotify - Biaya Rp0.",
    add_completion=False,
)
console = Console(legacy_windows=False)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("yt2sp.log", encoding="utf-8")],
)

# ── Helper ────────────────────────────────────────────────────────────────────

def _ensure_db() -> None:
    """Pastikan DB sudah diinisialisasi."""
    if not Path("yt2sp.db").exists():
        rprint("[red]Database belum ada. Jalankan dulu: yt2sp init[/red]")
        raise typer.Exit(1)
    database.init_db()


def _cfg() -> dict:
    return load_config()


# ── init ─────────────────────────────────────────────────────────────────────

@app.command()
def init() -> None:
    """Buat database dan config awal."""
    database.init_db()
    cfg_path = Path("config.toml")
    if not cfg_path.exists():
        cfg_path.write_text(
            "[resolve]\nrate_per_minute = 30\n\n[match]\nauto_accept_threshold = 0.85\nreview_threshold = 0.60\n\n[export]\nchunk_size = 50\n",
            encoding="utf-8",
        )
        rprint(f"[green]config.toml dibuat.[/green]")
    rprint("[green][OK] Database yt2sp.db siap.[/green]")
    rprint("\nLangkah berikutnya:")
    rprint("  [cyan]yt2sp auth-ytm[/cyan]   – setup autentikasi YouTube Music")
    rprint("  [cyan]yt2sp extract[/cyan]    – ekstrak playlist")


# ── auth-ytm ─────────────────────────────────────────────────────────────────

@app.command(name="auth-ytm")
def auth_ytm() -> None:
    """Setup autentikasi YouTube Music (browser headers)."""
    from ytmusicapi import YTMusic, setup_oauth

    rprint(Panel(
        "[bold]Setup Autentikasi YouTube Music[/bold]\n\n"
        "Pilih metode:\n"
        "  [cyan]1[/cyan] Headers browser (untuk playlist privat)\n"
        "  [cyan]2[/cyan] Tanpa auth (hanya playlist publik)",
        title="auth-ytm"
    ))
    choice = Prompt.ask("Pilih", choices=["1", "2"], default="2")

    if choice == "1":
        rprint("\n[yellow]Ikuti instruksi berikut:[/yellow]")
        rprint("1. Buka browser, buka [link]https://music.youtube.com[/link]")
        rprint("2. Tekan F12 → Network → refresh halaman")
        rprint("3. Cari request ke [cyan]music.youtube.com[/cyan]")
        rprint("4. Klik kanan request → Copy → Copy as cURL")
        rprint("5. Paste di bawah ini (tekan Enter dua kali jika selesai):\n")

        lines: list[str] = []
        rprint("[dim]Paste curl command (Enter kosong untuk selesai):[/dim]")
        while True:
            try:
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break

        # Simpan headers via ytmusicapi
        try:
            YTMusic.setup(filepath="ytm_auth.json", headers_raw="\n".join(lines))
            rprint("[green][OK] ytm_auth.json disimpan.[/green]")
        except Exception as exc:
            rprint(f"[red]Error: {exc}[/red]")
    else:
        rprint("[yellow]Mode publik – playlist privat tidak bisa diakses.[/yellow]")
        auth_file = Path("ytm_auth.json")
        if auth_file.exists():
            auth_file.unlink()
        rprint("[green][OK] Siap tanpa auth.[/green]")


# ── extract ───────────────────────────────────────────────────────────────────

@app.command()
def extract(
    playlist: str = typer.Option(None, "--playlist", "-p", help="ID playlist YTM"),
    all_playlists: bool = typer.Option(False, "--all", help="Semua playlist library"),
    liked: bool = typer.Option(False, "--liked", help="Liked Songs"),
) -> None:
    """Ekstrak playlist dari YouTube Music ke database."""
    _ensure_db()
    from yt2sp.ytm.extract import get_ytm, get_library_playlists, get_playlist_items, parse_track, get_liked_songs

    ytm = get_ytm()

    # Tentukan playlist yang akan diekstrak
    targets: list[tuple[str, str]] = []  # (yt_playlist_id, title)

    if liked:
        targets.append(("LIKED_SONGS", "Liked Songs"))

    if all_playlists:
        rprint("[cyan]Mengambil daftar playlist library...[/cyan]")
        lib = get_library_playlists(ytm)
        for p in lib:
            pid = p.get("playlistId") or p.get("browseId", "")
            title = p.get("title", "Untitled")
            if pid:
                targets.append((pid, title))
    elif playlist:
        from yt2sp.ytm.extract import clean_playlist_id
        targets.append((clean_playlist_id(playlist), "Playlist"))

    if not targets:
        rprint("[red]Tentukan --playlist ID/Link, --all, atau --liked.[/red]")
        raise typer.Exit(1)

    total_saved = 0
    for yt_pid, pl_title in targets:
        if yt_pid == "LIKED_SONGS":
            try:
                tracks_raw = get_liked_songs(ytm)
            except Exception as exc:
                rprint(f"[red]{exc}[/red]")
                continue
        else:
            try:
                from yt2sp.ytm.extract import get_playlist_details
                res = get_playlist_details(ytm, yt_pid)
                fetched_title, tracks_raw = res
                unavail = getattr(res, "unavailable_count", 0)
                if fetched_title:
                    pl_title = fetched_title
            except Exception as exc:
                rprint(f"[red]Gagal ambil playlist {yt_pid}: {exc}[/red]")
                continue

        rprint(f"\n[bold cyan]Mengekstrak:[/bold cyan] {pl_title} ({yt_pid}) - {len(tracks_raw)} lagu")
        if unavail > 0:
            rprint(f"[yellow]⚠️  Audit YouTube Music: {unavail} lagu tidak dapat dimuat karena telah dihapus atau dijadikan privat oleh uploader di YouTube.[/yellow]")

        # Simpan ke DB
        playlist_db_id = database.upsert_playlist(yt_pid, pl_title, len(tracks_raw), unavailable_count=unavail)

        saved = 0
        skipped = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Menyimpan lagu...", total=len(tracks_raw))
            for pos, raw in enumerate(tracks_raw):
                track = parse_track(raw)
                if track:
                    database.upsert_track(
                        track["video_id"],
                        track["title"],
                        track["artists"],
                        track["album"],
                        track["duration_ms"],
                        track["video_type"],
                    )
                    database.upsert_playlist_track(playlist_db_id, track["video_id"], pos)
                    saved += 1
                else:
                    skipped += 1
                progress.advance(task)

        rprint(f"  [green][OK] {saved} lagu disimpan[/green], {skipped} dilewati")
        total_saved += saved

    rprint(f"\n[bold green]Total: {total_saved} lagu tersimpan di database.[/bold green]")
    rprint("Jalankan [cyan]yt2sp resolve[/cyan] untuk mulai matching ke Spotify.")


# ── resolve ───────────────────────────────────────────────────────────────────

@app.command()
def resolve(
    limit: int = typer.Option(None, "--limit", "-n", help="Batas jumlah lagu"),
    rate: float = typer.Option(None, "--rate", "-r", help="Request per menit"),
) -> None:
    """Jalankan resolver Spotify untuk semua lagu pending (bisa dihentikan & dilanjutkan)."""
    _ensure_db()
    cfg = _cfg()
    r = rate or cfg["resolve"]["rate_per_minute"]

    pending = database.get_pending_tracks()
    total = len(pending) if not limit else min(len(pending), limit)

    if total == 0:
        rprint("[green]Tidak ada lagu yang perlu diproses.[/green]")
        return

    rprint(f"\n[bold]Memproses {total} lagu[/bold] @ {r} req/menit\n")
    rprint("[dim]Tekan Ctrl+C untuk berhenti – progres otomatis tersimpan.[/dim]\n")

    from yt2sp.resolve.pipeline import run_resolve

    counts = {"processed": 0, "auto": 0, "review": 0, "failed": 0, "skipped": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Resolving...", total=total)

        def on_progress(video_id: str, status: str, score: float) -> None:
            counts["processed"] += 1
            if status == "resolved_auto":
                counts["auto"] += 1
                label = "[green][OK] auto[/green]"
            elif status == "needs_review":
                counts["review"] += 1
                label = "[yellow]? review[/yellow]"
            elif status == "skipped":
                counts["skipped"] += 1
                label = "[dim]skip[/dim]"
            else:
                counts["failed"] += 1
                label = "[red][X] gagal[/red]"
            progress.update(
                task,
                advance=1,
                description=f"{label} {video_id[:11]}... score={score:.2f}",
            )

        try:
            run_resolve(
                limit=limit,
                rate_per_minute=r,
                auto_threshold=cfg["match"]["auto_accept_threshold"],
                review_threshold=cfg["match"]["review_threshold"],
                title_weight=cfg["match"]["title_weight"],
                artist_weight=cfg["match"]["artist_weight"],
                duration_tolerance=cfg["match"]["duration_tolerance_pct"],
                on_progress=on_progress,
            )
        except KeyboardInterrupt:
            rprint("\n[yellow]Dihentikan – progres tersimpan.[/yellow]")

    # Ringkasan
    t = Table(title="Hasil Resolve", show_header=True)
    t.add_column("Status")
    t.add_column("Jumlah", justify="right")
    t.add_row("[green]Auto accepted[/green]", str(counts["auto"]))
    t.add_row("[yellow]Perlu review[/yellow]", str(counts["review"]))
    t.add_row("[red]Gagal[/red]", str(counts["failed"]))
    t.add_row("[dim]Dilewati[/dim]", str(counts["skipped"]))
    console.print(t)

    if counts["review"] > 0:
        rprint(f"\nJalankan [cyan]yt2sp review[/cyan] untuk {counts['review']} lagu yang perlu dicek.")


# ── review ────────────────────────────────────────────────────────────────────

@app.command()
def review() -> None:
    """Review interaktif lagu yang perlu dikonfirmasi."""
    _ensure_db()
    tracks = database.get_review_tracks()

    if not tracks:
        rprint("[green]Tidak ada lagu yang perlu direview.[/green]")
        return

    rprint(f"\n[bold]{len(tracks)} lagu butuh review.[/bold]\n")
    rprint("[dim]Perintah: [a]ccept / [r]eject / [s]kip / [m]anual URI / [q]uit[/dim]\n")

    for t in tracks:
        artists = json.loads(t["artists"]) if t["artists"] else []

        console.rule()
        rprint(f"[bold]YouTube Music:[/bold] {t['title']} – {', '.join(artists)}")
        rprint(f"[bold]Spotify match:[/bold] {t['result_title']} – {t['result_artist']}")
        rprint(f"[bold]Score:[/bold] {t['score']:.3f}  |  [bold]Alasan:[/bold] {t['reason'] or '-'}")
        rprint(f"[bold]Spotify URI:[/bold] spotify:track:{t['spotify_id']}")
        rprint(f"[bold]Cari manual:[/bold] https://open.spotify.com/search/{t['title'].replace(' ', '%20')}")

        while True:
            action = Prompt.ask(
                "Aksi",
                choices=["a", "r", "s", "m", "q"],
                default="s",
            )
            if action == "a":
                database.set_match(
                    t["video_id"],
                    spotify_id=t["spotify_id"],
                    tier=t["tier"],
                    score=t["score"],
                    status="accepted",
                    result_title=t["result_title"],
                    result_artist=t["result_artist"],
                    decided_by="human",
                    reason="diterima manual",
                )
                rprint("[green][OK] Diterima[/green]")
                break
            elif action == "r":
                database.set_match(
                    t["video_id"],
                    spotify_id=None,
                    tier=t["tier"],
                    score=t["score"],
                    status="rejected",
                    decided_by="human",
                    reason="ditolak manual",
                )
                rprint("[red][X] Ditolak[/red]")
                break
            elif action == "m":
                raw_uri = Prompt.ask("Paste Spotify URI atau link")
                # Ekstrak ID dari berbagai format
                sp_id = _extract_spotify_id(raw_uri)
                if sp_id:
                    database.set_match(
                        t["video_id"],
                        spotify_id=sp_id,
                        tier=t["tier"],
                        score=1.0,
                        status="accepted",
                        decided_by="human_manual",
                        reason="diisi manual",
                    )
                    rprint(f"[green][OK] Disimpan: spotify:track:{sp_id}[/green]")
                else:
                    rprint("[red]Format tidak valid. Contoh: spotify:track:4cOdK2wGLETKBW3PvgPWqT[/red]")
                    continue
                break
            elif action == "s":
                rprint("[dim]Dilewati[/dim]")
                break
            elif action == "q":
                rprint("[yellow]Review dihentikan.[/yellow]")
                return


def _extract_spotify_id(raw: str) -> str | None:
    """Ekstrak track ID dari URI atau URL Spotify."""
    import re
    # spotify:track:ID
    m = re.search(r"spotify:track:([A-Za-z0-9]{22})", raw)
    if m:
        return m.group(1)
    # https://open.spotify.com/track/ID
    m = re.search(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", raw)
    if m:
        return m.group(1)
    # Jika cuma ID langsung (22 chars)
    raw = raw.strip()
    if re.match(r"^[A-Za-z0-9]{22}$", raw):
        return raw
    return None


# ── export ────────────────────────────────────────────────────────────────────

@app.command()
def export(
    output: Path = typer.Option(Path("output"), "--output", "-o", help="Direktori output"),
    chunk: int = typer.Option(None, "--chunk", "-c", help="URI per blok"),
    dedup: bool = typer.Option(False, "--dedup", help="Hapus duplikat URI"),
    by_genre: bool = typer.Option(False, "--by-genre", "-g", help="Pisahkan export playlist berdasarkan Genre"),
) -> None:
    """Export URI Spotify ke file dan laporan CSV (bisa dipisah per Genre)."""
    _ensure_db()
    cfg = _cfg()
    chunk_size = chunk or cfg["export"]["chunk_size"]
    out_dir = output

    from yt2sp.export.writer import write_uri_blocks
    from yt2sp.export.report import write_csv_report

    playlists = database.get_all_playlists()
    if not playlists:
        rprint("[red]Belum ada playlist di database. Jalankan yt2sp extract dulu.[/red]")
        raise typer.Exit(1)

    total_files = 0
    for pl in playlists:
        tracks = database.get_playlist_tracks(pl["id"])
        pl_title = pl["title"] or f"playlist_{pl['yt_playlist_id']}"

        if by_genre:
            # Ambil semua genre unik di playlist ini
            genres_summary = database.get_playlist_genres(pl["id"])
            if not genres_summary:
                rprint(f"[yellow]⚠ {pl_title}: belum ada lagu yang cocok untuk diexport.[/yellow]")
                continue

            rprint(f"\n[bold cyan]Mengekspor playlist per Genre:[/bold cyan] {pl_title}")
            for g_row in genres_summary:
                genre_name = g_row["genre"]
                g_tracks = database.get_playlist_tracks_for_genre(pl["id"], genre_name)
                g_uris = [f"spotify:track:{t['spotify_id']}" for t in g_tracks if t["spotify_id"]]
                if g_uris:
                    sub_title = f"{pl_title} - {genre_name}"
                    files = write_uri_blocks(sub_title, g_uris, out_dir / "uris", chunk_size, dedup)
                    rprint(f"  [green][OK] {genre_name}:[/green] {len(g_uris)} lagu -> {len(files)} file")
                    total_files += len(files)
        else:
            # Export standar (semua lagu dalam 1 playlist)
            accepted_uris = []
            for t in tracks:
                status = t["status"]
                sp_id = t["spotify_id"]
                if status in ("accepted", "resolved_auto") and sp_id:
                    accepted_uris.append(f"spotify:track:{sp_id}")

            if accepted_uris:
                files = write_uri_blocks(pl_title, accepted_uris, out_dir / "uris", chunk_size, dedup)
                rprint(f"[green][OK] {pl_title}:[/green] {len(accepted_uris)} lagu -> {len(files)} file")
                total_files += len(files)
            else:
                rprint(f"[yellow]⚠ {pl_title}:[/yellow] tidak ada lagu yang lolos")

        # Buat CSV report
        csv_path = write_csv_report(pl_title, tracks, out_dir / "reports")
        rprint(f"  [dim]Report CSV: {csv_path}[/dim]")

    rprint(f"\n[bold green][OK] {total_files} file URI tersimpan di {out_dir / 'uris'}[/bold green]")
    rprint("\n[bold]Langkah di Spotify Desktop:[/bold]")
    rprint("1. Buat playlist baru untuk tiap file / genre yang diinginkan")
    rprint("2. Buka file .txt, salin semua baris (Ctrl+A -> Ctrl+C)")
    rprint("3. Di Spotify Desktop, sorot baris lagu -> tekan Ctrl+V")


# ── tag-genre ─────────────────────────────────────────────────────────────────

@app.command(name="tag-genre")
def tag_genre(
    all_uncategorized: bool = typer.Option(
        True,
        "--all-uncategorized/--only-null",
        help="Sertakan lagu yang masih berstatus 'Uncategorized' untuk divalidasi ulang dengan sumber baru",
    )
) -> None:
    """Deteksi dan validasi Genre otomatis (Multi-Source: iTunes + Deezer + Heuristik)."""
    _ensure_db()
    from yt2sp.resolve.genre import fetch_genre_validated

    missing = database.get_tracks_without_genre(include_uncategorized=all_uncategorized)
    if not missing:
        rprint("[green][OK] Semua lagu di database sudah memiliki label Genre.[/green]")
        return

    rprint(f"\n[bold]Mendeteksi & Memvalidasi Genre untuk {len(missing)} lagu...[/bold]")
    stats = {
        "validated_agreement": 0,
        "cross_validated": 0,
        "single_source": 0,
        "heuristic": 0,
        "uncategorized": 0,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Mendeteksi genre...", total=len(missing))
        for t in missing:
            artists = json.loads(t["artists"]) if t["artists"] else []
            r_title = t["result_title"] if "result_title" in t.keys() else None
            r_artist = t["result_artist"] if "result_artist" in t.keys() else None
            gres = fetch_genre_validated(
                t["title"] or "",
                artists,
                result_title=r_title,
                result_artist=r_artist,
            )
            database.update_track_genre(t["video_id"], gres.genre, source=gres.source)

            # Record stats
            if gres.status == "validated_agreement":
                stats["validated_agreement"] += 1
            elif gres.status == "cross_validated":
                stats["cross_validated"] += 1
            elif gres.status.startswith("single_source"):
                stats["single_source"] += 1
            elif gres.status == "heuristic":
                stats["heuristic"] += 1
            else:
                stats["uncategorized"] += 1

            progress.update(task, advance=1, description=f"[cyan]{gres.genre}[/cyan] ({gres.source[:20]}) : {t['title'][:20]}")

    rprint("\n[bold green][OK] Selesai memberi label & memvalidasi genre![/bold green]")
    val_table = Table(title="Hasil Validasi Multi-Sumber Genre", show_header=True, header_style="bold cyan")
    val_table.add_column("Kategori Validasi", style="white")
    val_table.add_column("Jumlah Lagu", justify="right", style="green")
    val_table.add_column("Deskripsi", style="dim")
    val_table.add_row("Tervalidasi (Agreement)", str(stats["validated_agreement"]), "Kedua sumber (iTunes + Deezer) sepakat")
    val_table.add_row("Validasi Silang (Cross-Validated)", str(stats["cross_validated"]), "Subgenre spesifik tervalidasi antar sumber")
    val_table.add_row("Sumber Tunggal (Single Source)", str(stats["single_source"]), "Ditemukan lewat Deezer atau iTunes saja")
    val_table.add_row("Heuristik Kontekstual", str(stats["heuristic"]), "Dikenali lewat kata kunci konten (Anime/OST/Dangdut)")
    val_table.add_row("Belum Terkategori (Uncategorized)", str(stats["uncategorized"]), "Tidak ditemukan di semua katalog")
    console.print(val_table)
    rprint("Jalankan [cyan]yt2sp split[/cyan] untuk melihat pembagian genre atau [cyan]yt2sp export --by-genre[/cyan] untuk export terpisah.")


# ── split ─────────────────────────────────────────────────────────────────────

@app.command()
def split() -> None:
    """Lihat pembagian lagu berdasarkan Genre di tiap playlist."""
    _ensure_db()
    playlists = database.get_all_playlists()
    if not playlists:
        rprint("[red]Belum ada playlist. Jalankan extract dulu.[/red]")
        raise typer.Exit(1)

    for pl in playlists:
        genres = database.get_playlist_genres(pl["id"])
        pl_title = pl["title"] or f"playlist_{pl['yt_playlist_id']}"
        t = Table(title=f"Pembagian Genre: {pl_title}", show_header=True, header_style="bold magenta")
        t.add_column("Genre / Kategori", style="cyan")
        t.add_column("Jumlah Lagu Cocok", justify="right")

        total = 0
        for row in genres:
            t.add_row(row["genre"], str(row["track_count"]))
            total += row["track_count"]

        t.add_section()
        t.add_row("[bold]Total Lagu Siap Pisah[/bold]", f"[bold]{total}[/bold]")
        console.print(t)
        print()

    rprint("Ketik [cyan]yt2sp export --by-genre[/cyan] untuk langsung membuat file playlist terpisah per genre!")



# ── status ────────────────────────────────────────────────────────────────────

@app.command()
def status() -> None:
    """Tampilkan ringkasan progres."""
    _ensure_db()
    s = database.get_status_summary()

    done = s["resolved_auto"] + s["accepted"]
    total = s["total"]
    pct = done / total * 100 if total else 0

    t = Table(title="Status yt2sp", show_header=True, header_style="bold cyan")
    t.add_column("Kategori")
    t.add_column("Jumlah", justify="right")
    t.add_column("Keterangan")

    t.add_row("Total lagu", str(total), "dari semua playlist")
    t.add_row("[dim]Pending[/dim]", str(s["pending"]), "belum diproses")
    t.add_row("[green]Auto accepted[/green]", str(s["resolved_auto"]), "skor ≥ threshold auto")
    t.add_row("[green]Diterima manual[/green]", str(s["accepted"]), "dari review")
    t.add_row("[yellow]Perlu review[/yellow]", str(s["needs_review"]), "jalankan: yt2sp review")
    t.add_row("[red]Gagal[/red]", str(s["failed"]), "tidak ditemukan")
    t.add_row("[dim]Dilewati[/dim]", str(s["skipped"]), "non-musik")
    t.add_row("[bold]TOTAL SIAP EXPORT[/bold]", f"[bold]{done}[/bold]", f"{pct:.1f}% dari total")

    console.print(t)

    playlists = database.get_all_playlists()
    if playlists:
        rprint(f"\n[bold]Playlist di database ({len(playlists)}):[/bold]")
        for p in playlists:
            rprint(f"  • {p['title']} [{p['yt_playlist_id']}] – {p['track_count']} lagu")


# ── golden ────────────────────────────────────────────────────────────────────

@app.command()
def golden(
    action: str = typer.Argument(..., help="import | score"),
    csv_file: Path = typer.Option(None, "--file", "-f", help="CSV untuk import"),
) -> None:
    """Kelola golden set untuk evaluasi akurasi matching."""
    _ensure_db()

    if action == "import":
        if not csv_file or not csv_file.exists():
            rprint("[red]Tentukan file CSV dengan --file. Kolom: video_id, spotify_id, notes[/red]")
            raise typer.Exit(1)
        count = 0
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                database.upsert_golden(
                    row.get("video_id", "").strip(),
                    row.get("spotify_id", "").strip(),
                    row.get("notes", "").strip(),
                )
                count += 1
        rprint(f"[green][OK] {count} entri golden set diimpor.[/green]")

    elif action == "score":
        golden_rows = database.get_golden_set()
        if not golden_rows:
            rprint("[red]Golden set kosong. Jalankan: yt2sp golden import --file data.csv[/red]")
            raise typer.Exit(1)

        total = len(golden_rows)
        correct = 0
        found = 0
        for g in golden_rows:
            if g["matched_id"]:
                found += 1
                if g["matched_id"] == g["spotify_id_human"]:
                    correct += 1

        precision = correct / found * 100 if found else 0
        coverage = found / total * 100 if total else 0

        rprint(f"\n[bold]Golden Set Score:[/bold]")
        rprint(f"  Total lagu        : {total}")
        rprint(f"  Ditemukan         : {found} ({coverage:.1f}%)")
        rprint(f"  Presisi (benar)   : {correct} ({precision:.1f}%)")
        rprint(f"  Target presisi    : ≥ 98%  {'[green][OK][/green]' if precision >= 98 else '[red][X][/red]'}")
        rprint(f"  Target cakupan    : ≥ 80%  {'[green][OK][/green]' if coverage >= 80 else '[red][X][/red]'}")
    else:
        rprint("[red]Aksi tidak dikenal. Gunakan: import | score[/red]")
        raise typer.Exit(1)


# ── smoke-test ────────────────────────────────────────────────────────────────

@app.command(name="smoke-test")
def smoke_test() -> None:
    """M0: Generate 5 URI uji untuk Ctrl+V paste test di Spotify Desktop."""
    uris = [
        "spotify:track:4cOdK2wGLETKBW3PvgPWqT",  # Rick Astley - Never Gonna Give You Up
        "spotify:track:2dIBMHByUGcNPzmYBJ6OAj",  # Hindia - Evaluasi
        "spotify:track:2hHeGD57S0BcopfVcmehdl",  # Tulus - Hati-Hati di Jalan
        "spotify:track:3AJwUDP919kvQ9QcozQPxg",  # Coldplay - Yellow
        "spotify:track:2OBofMJx94NryV2SK8p8Zf",  # Queen - Bohemian Rhapsody
    ]

    out = Path("smoke_test_uris.txt")
    out.write_text("\n".join(uris) + "\n", encoding="utf-8")

    rprint(Panel(
        "[bold]M0 Smoke Test – Instruksi Paste[/bold]\n\n"
        "5 URI telah disimpan ke: [cyan]smoke_test_uris.txt[/cyan]\n\n"
        "[bold]Cara uji:[/bold]\n"
        "1. Buka [cyan]smoke_test_uris.txt[/cyan]\n"
        "2. Pilih semua teks (Ctrl+A) → Salin (Ctrl+C)\n"
        "3. Buka Spotify Desktop\n"
        "4. Buat playlist BARU yang kosong\n"
        "5. Klik di dalam area playlist\n"
        "6. Tekan [bold]Ctrl+V[/bold]\n\n"
        "[bold]Hasilnya seharusnya:[/bold]\n"
        "• Never Gonna Give You Up – Rick Astley\n"
        "• Evaluasi – Hindia\n"
        "• Hati-Hati di Jalan – Tulus\n"
        "• Yellow – Coldplay\n"
        "• Bohemian Rhapsody – Queen\n\n"
        "[yellow]Kalau berhasil → lanjut yt2sp extract[/yellow]\n"
        "[red]Kalau gagal → Spotify Desktop versi Anda tidak support paste URI[/red]",
        title="Smoke Test M0",
        border_style="cyan",
    ))


# ── ui ────────────────────────────────────────────────────────────────────────

@app.command()
def ui(
    port: int = typer.Option(5000, "--port", "-p", help="Port Web UI server"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Jangan otomatis buka browser"),
) -> None:
    """Buka Web UI di browser (antarmuka visual yang mudah digunakan)."""
    _ensure_db()
    from yt2sp.ui.server import start_server
    start_server(port=port, open_browser=not no_browser)


# ── reset ─────────────────────────────────────────────────────────────────────

@app.command(name="reset")
def reset_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Hapus langsung tanpa konfirmasi"),
    clear_cache: bool = typer.Option(False, "--clear-cache", help="Hapus juga cache pencarian"),
) -> None:
    """Hapus semua data lagu dan playlist di database (mulai dari 0)."""
    _ensure_db()
    if not force:
        confirm = Confirm.ask(
            "[bold red]Apakah Anda yakin ingin menghapus SEMUA lagu dan playlist?[/bold red]\nSemua data di database akan direset ke 0",
            default=False,
        )
        if not confirm:
            rprint("[yellow]Batal reset.[/yellow]")
            return
    database.reset_all_data(clear_cache=clear_cache)
    rprint("[green][OK] Database berhasil direset. Semua data lagu dikosongkan ke 0.[/green]")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
