"""Pencarian dan validasi Genre lagu multi-sumber (iTunes + Deezer + Heuristik).

Mendukung validasi silang antara sumber lama (iTunes) dan sumber baru (Deezer),
dengan resolusi spesifisitas subgenre dan fallback heuristik kontekstual.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Kategori genre standar untuk mengelompokkan sub-genre yang mirip
GENRE_GROUPS = {
    # Indo / Nusantara
    "Indo Pop": "Indonesian Pop",
    "Indonesian Pop": "Indonesian Pop",
    "Dangdut": "Dangdut & Koplo",
    "Koplo": "Dangdut & Koplo",
    "Regional Pop": "Indonesian Regional",
    "Indonesian Regional": "Indonesian Regional",
    "Indonesian Indie": "Indonesian Pop",
    "Sunda": "Indonesian Regional",
    "Jawa": "Indonesian Regional",
    "Pop Minang": "Indonesian Regional",

    # Pop & R&B
    "Pop": "Pop",
    "K-Pop": "K-Pop",
    "J-Pop": "J-Pop",
    "Asian Music": "Pop",
    "Mandopop": "Mandopop",
    "Cantopop": "Mandopop",
    "R&B/Soul": "R&B / Soul",
    "R&B": "R&B / Soul",
    "Soul": "R&B / Soul",
    "Neo-Soul": "R&B / Soul",

    # Rock & Metal
    "Rock": "Rock",
    "Alternative": "Alternative & Indie",
    "Alternative Rock": "Alternative & Indie",
    "Indie Rock": "Alternative & Indie",
    "Indie Pop": "Alternative & Indie",
    "Indie": "Alternative & Indie",
    "Hard Rock": "Rock & Metal",
    "Heavy Metal": "Rock & Metal",
    "Metal": "Rock & Metal",
    "Punk": "Rock & Metal",
    "Post-Rock": "Rock",
    "Pop/Rock": "Rock",

    # Hip-Hop & Rap
    "Hip-Hop/Rap": "Hip-Hop & Rap",
    "Hip-Hop": "Hip-Hop & Rap",
    "Rap": "Hip-Hop & Rap",
    "Rap/Hip Hop": "Hip-Hop & Rap",
    "Trap": "Hip-Hop & Rap",

    # Electronic & Dance
    "Dance": "Electronic & Dance",
    "Electro": "Electronic & Dance",
    "Electronic": "Electronic & Dance",
    "House": "Electronic & Dance",
    "EDM": "Electronic & Dance",
    "Techno": "Electronic & Dance",
    "Dubstep": "Electronic & Dance",
    "Trance": "Electronic & Dance",
    "Drum & Bass": "Electronic & Dance",
    "Downtempo": "Electronic & Dance",
    "Ambient": "Electronic & Dance",

    # Acoustic & Folk
    "Singer/Songwriter": "Acoustic & Folk",
    "Folk": "Acoustic & Folk",
    "Acoustic": "Acoustic & Folk",
    "Country": "Acoustic & Folk",
    "Folk-Rock": "Acoustic & Folk",

    # Anime & Vocaloid & Game
    "Anime": "Anime",
    "Vocaloid": "Anime",
    "Video Game": "Soundtrack & Classical",
    "Soundtrack": "Soundtrack & Classical",
    "Films/Games": "Soundtrack & Classical",
    "Classical": "Soundtrack & Classical",
    "Film Score": "Soundtrack & Classical",

    # Lainnya
    "Jazz": "Jazz & Blues",
    "Blues": "Jazz & Blues",
    "Reggae": "Reggae & Ska",
    "Ska": "Reggae & Ska",
    "Latin": "Latin & Worldwide",
    "Worldwide": "Latin & Worldwide",
    "World": "Latin & Worldwide",
}

# Subgenre spesifik yang diprioritaskan di atas genre umum (Pop, Rock, Asian Music)
SPECIFIC_GENRES = {
    "Indonesian Pop",
    "Dangdut & Koplo",
    "Indonesian Regional",
    "K-Pop",
    "J-Pop",
    "R&B / Soul",
    "Alternative & Indie",
    "Rock & Metal",
    "Hip-Hop & Rap",
    "Electronic & Dance",
    "Acoustic & Folk",
    "Anime",
    "Soundtrack & Classical",
    "Jazz & Blues",
}


@dataclass
class GenreValidationResult:
    """Hasil deteksi dan validasi silang genre."""
    genre: str
    source: str
    itunes_genre: str | None
    deezer_genre: str | None
    heuristic_genre: str | None
    confidence: float
    status: str


def clean_track_query(title: str, artist: str = "") -> str:
    """Bersihkan judul lagu dari noise YouTube (Official MV, Cover, tag bracket)."""
    t = re.sub(r'\[.*?\]|\(.*?\)|【.*?】', ' ', title)
    t = re.sub(
        r'\b(official\s+video|official\s+music\s+video|music\s+video|lyric\s+video|audio|mv|visualizer|lirik)\b',
        ' ',
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r'\s+', ' ', t).strip()
    if " | " in t:
        parts = t.split(" | ")
        t = parts[0].strip()
    return f"{t} {artist}".strip()


def detect_genre_heuristic(title: str, artist: str = "") -> str | None:
    """Deteksi genre berbasis kata kunci kontekstual (Anime, Vocaloid, Game OST, Dangdut, dll)."""
    text = f"{title} {artist}".lower()

    # 1. Soundtrack & Game
    if any(k in text for k in ["hoyo-mix", "honkai", "genshin impact", "soundtrack", " ost", "bgm", "theme song", "original soundtrack"]):
        return "Soundtrack & Classical"

    # 2. Anime & Vocaloid
    if any(k in text for k in ["vocaloid", "初音ミク", "hatsune miku", "synth v", "gumi", "kagamine", "megurine", "project sekai", "プロセカ", "歌ってみた"]):
        return "Anime"

    # 3. Dangdut & Koplo
    if any(k in text for k in ["dangdut", "koplo", "kendang", "campursari", "om adella", "new pallapa"]):
        return "Dangdut & Koplo"

    # 4. Electronic / Lofi
    if any(k in text for k in ["lofi", "lo-fi", "chillhop", "nightcore", "remix edm", "bass boost"]):
        return "Electronic & Dance"

    return None


def fetch_itunes_raw(query: str, timeout: int = 4) -> str | None:
    """Fetch genre mentah dari Apple iTunes Search API (Old Source - 100% Gratis)."""
    if not query:
        return None
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "yt2sp/1.0 (https://github.com/yt2sp)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            if data.get("resultCount", 0) > 0:
                raw = data["results"][0].get("primaryGenreName", "").strip()
                return raw or None
    except Exception as exc:
        logger.debug("iTunes search error untuk '%s': %s", query, exc)
    return None


def fetch_deezer_raw(query: str, timeout: int = 4) -> str | None:
    """Fetch genre mentah dari Deezer Catalog API (New Source - 100% Gratis)."""
    if not query:
        return None
    url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "yt2sp/1.0 (https://github.com/yt2sp)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            if data.get("data"):
                track = data["data"][0]
                album_id = track.get("album", {}).get("id")
                if album_id:
                    aurl = f"https://api.deezer.com/album/{album_id}"
                    with urllib.request.urlopen(
                        urllib.request.Request(aurl, headers={"User-Agent": "yt2sp/1.0"}),
                        timeout=timeout,
                    ) as ar:
                        adata = json.loads(ar.read().decode("utf-8"))
                        genres = adata.get("genres", {}).get("data", [])
                        if genres:
                            return genres[0].get("name", "").strip() or None
    except Exception as exc:
        logger.debug("Deezer search error untuk '%s': %s", query, exc)
    return None


def validate_and_reconcile_genre(
    itunes_raw: str | None,
    deezer_raw: str | None,
    heuristic_raw: str | None,
    *,
    group: bool = True,
) -> GenreValidationResult:
    """
    Validasi silang antara sumber lama (iTunes) dan sumber baru (Deezer),
    dengan resolusi ambiguitas dan fallback context heuristic.
    """
    itunes_grp = GENRE_GROUPS.get(itunes_raw, itunes_raw) if itunes_raw and group else itunes_raw
    deezer_grp = GENRE_GROUPS.get(deezer_raw, deezer_raw) if deezer_raw and group else deezer_raw

    # 1. KEDUA SUMBER DITEMUKAN (Validation Active)
    if itunes_grp and deezer_grp:
        # Kesepakatan Penuh (Agreement)
        if itunes_grp == deezer_grp:
            return GenreValidationResult(
                genre=itunes_grp,
                source="itunes+deezer",
                itunes_genre=itunes_raw,
                deezer_genre=deezer_raw,
                heuristic_genre=heuristic_raw,
                confidence=1.0,
                status="validated_agreement",
            )

        # Resolusi Spesifisitas (subgenre spesifik mengalahkan generic 'Pop'/'Rock'/'Asian Music')
        if itunes_grp in SPECIFIC_GENRES and deezer_grp in ("Pop", "Rock", "Asian Music"):
            return GenreValidationResult(
                genre=itunes_grp,
                source=f"cross_validated (itunes specific: {itunes_raw})",
                itunes_genre=itunes_raw,
                deezer_genre=deezer_raw,
                heuristic_genre=heuristic_raw,
                confidence=0.92,
                status="cross_validated",
            )
        if deezer_grp in SPECIFIC_GENRES and itunes_grp in ("Pop", "Rock", "Asian Music"):
            return GenreValidationResult(
                genre=deezer_grp,
                source=f"cross_validated (deezer specific: {deezer_raw})",
                itunes_genre=itunes_raw,
                deezer_genre=deezer_raw,
                heuristic_genre=heuristic_raw,
                confidence=0.92,
                status="cross_validated",
            )

        # Jika kedua sumber memberikan genre berbeda (misal: R&B / Soul vs Pop)
        # Prioritaskan Deezer album genre resmi atau iTunes
        return GenreValidationResult(
            genre=deezer_grp,
            source=f"cross_validated ({deezer_raw} vs {itunes_raw})",
            itunes_genre=itunes_raw,
            deezer_genre=deezer_raw,
            heuristic_genre=heuristic_raw,
            confidence=0.85,
            status="cross_validated",
        )

    # 2. HANYA DEEZER (Sumber baru melengkapi ketidakadaan sumber lama)
    if deezer_grp:
        return GenreValidationResult(
            genre=deezer_grp,
            source="deezer",
            itunes_genre=None,
            deezer_genre=deezer_raw,
            heuristic_genre=heuristic_raw,
            confidence=0.85,
            status="single_source_deezer",
        )

    # 3. HANYA ITUNES (Sumber lama)
    if itunes_grp:
        return GenreValidationResult(
            genre=itunes_grp,
            source="itunes",
            itunes_genre=itunes_raw,
            deezer_genre=None,
            heuristic_genre=heuristic_raw,
            confidence=0.85,
            status="single_source_itunes",
        )

    # 4. FALLBACK KE HEURISTIK KONTEKSTUAL (Anime, Vocaloid, Game OST, Dangdut, dll)
    if heuristic_raw:
        h_grp = GENRE_GROUPS.get(heuristic_raw, heuristic_raw) if group else heuristic_raw
        return GenreValidationResult(
            genre=h_grp,
            source="context_heuristic",
            itunes_genre=None,
            deezer_genre=None,
            heuristic_genre=heuristic_raw,
            confidence=0.75,
            status="heuristic",
        )

    # 5. TIDAK DITEMUKAN
    return GenreValidationResult(
        genre="Uncategorized",
        source="none",
        itunes_genre=None,
        deezer_genre=None,
        heuristic_genre=None,
        confidence=0.0,
        status="uncategorized",
    )


def _fetch_both_raw(q: str, timeout: int) -> tuple[str | None, str | None]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_it = ex.submit(fetch_itunes_raw, q, timeout)
        f_dz = ex.submit(fetch_deezer_raw, q, timeout)
        return f_it.result(), f_dz.result()


def fetch_genre_validated(
    title: str,
    artists: list[str],
    *,
    result_title: str | None = None,
    result_artist: str | None = None,
    timeout: int = 4,
    group: bool = True,
) -> GenreValidationResult:
    """
    Cari genre lagu dari multi-sumber (iTunes + Deezer + Heuristik) dan lakukan validasi silang.
    """
    primary = artists[0] if artists else ""

    # Prioritaskan pencarian dengan clean title & clean artist (dari match Spotify jika ada)
    clean_t = result_title or title
    clean_a = result_artist or primary
    query = clean_track_query(clean_t, clean_a)

    itunes_raw, deezer_raw = _fetch_both_raw(query, timeout)

    # Fallback retry jika belum ketemu dan query awal berbeda dari title asli
    if not itunes_raw and not deezer_raw and (result_title or result_artist):
        fallback_q = clean_track_query(title, primary)
        if fallback_q != query:
            itunes_raw, deezer_raw = _fetch_both_raw(fallback_q, timeout)

    heuristic = detect_genre_heuristic(title, primary)
    return validate_and_reconcile_genre(itunes_raw, deezer_raw, heuristic, group=group)


def fetch_genre(
    title: str,
    artists: list[str],
    *,
    result_title: str | None = None,
    result_artist: str | None = None,
    timeout: int = 4,
    group: bool = True,
) -> str:
    """
    Cari genre lagu dari multi-sumber tervalidasi.
    Kompatibel penuh dengan implementasi pemanggil sebelumnya.
    """
    res = fetch_genre_validated(
        title,
        artists,
        result_title=result_title,
        result_artist=result_artist,
        timeout=timeout,
        group=group,
    )
    return res.genre
