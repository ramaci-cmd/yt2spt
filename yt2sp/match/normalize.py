"""Normalisasi judul & artis untuk fuzzy matching.

Aturan:
- Lowercase + unicode ke ASCII (unidecode)
- Buang noise: 'official video', 'official audio', 'lyrics', 'lyric video',
  'music video', 'mv', 'hd', '4k', 'remaster', 'remastered', feat./ft.,
  tanda kurung biasa (kecuali berisi penanda pembeda)
- JAGA penanda pembeda: live, acoustic, remix, cover, instrumental,
  karaoke, slowed, sped up, nightcore, lofi
- Buang tanda baca berlebih
"""
from __future__ import annotations

import re
from unidecode import unidecode

# Penanda yang HARUS dijaga (jika ada di salah satu sisi)
DISTINCTIVE_MARKERS = {
    "live", "acoustic", "remix", "cover", "instrumental",
    "karaoke", "slowed", "sped up", "nightcore", "lofi", "lo-fi",
    "unplugged", "demo", "radio edit", "extended",
}

# Kata noise yang dihapus (tidak di dalam tanda kurung berisi penanda)
_NOISE_WORDS = [
    r"official\s+(?:music\s+)?video",
    r"official\s+audio",
    r"official\s+lyric\s+video",
    r"official\s+visualizer",
    r"lyric(?:s)?\s+video",
    r"lyrics?",
    r"music\s+video",
    r"\bmv\b",
    r"\b(?:full\s+)?hd\b",
    r"\b4k\b",
    r"\b(?:19|20)\d{2}\s+remaster(?:ed)?",
    r"remaster(?:ed)?",
    r"explicit\s+version",
    r"clean\s+version",
    r"audio\s+only",
    r"visualizer",
    r"performance\s+video",
]
_NOISE_RE = re.compile(
    r"(?:" + "|".join(_NOISE_WORDS) + r")",
    re.IGNORECASE,
)

# feat / ft – perlu hapus untuk artis matching
_FEAT_RE = re.compile(
    r"\s*(?:feat(?:uring)?|ft)\.?\s+[^)\]]*",
    re.IGNORECASE,
)


def has_distinctive_marker(text: str) -> set[str]:
    """Return set penanda pembeda yang ditemukan di text."""
    low = text.lower()
    return {m for m in DISTINCTIVE_MARKERS if m in low}


def normalize_title(title: str, *, keep_feat: bool = False) -> str:
    """Normalisasi judul lagu."""
    s = title

    # Hapus feat dari judul (kecuali diminta)
    if not keep_feat:
        s = _FEAT_RE.sub("", s)

    # Hapus noise di dalam tanda kurung HANYA jika kontennya bukan penanda pembeda
    def _strip_parens(m: re.Match) -> str:
        inner = m.group(1).lower()
        if any(marker in inner for marker in DISTINCTIVE_MARKERS):
            return m.group(0)  # jaga seluruh kurung
        return ""  # hapus kurung + isinya

    s = re.sub(r"\(([^)]*)\)", _strip_parens, s)
    s = re.sub(r"\[([^\]]*)\]", lambda m: _strip_parens(re.match(r"\((.*)\)", f"({m.group(1)})") or m), s)

    # Hapus noise words yang masih tersisa
    s = _NOISE_RE.sub("", s)

    # Hapus tanda hubung di awal/akhir dan spasi berlebih
    s = re.sub(r"[-|_]+$", "", s.strip())
    s = re.sub(r"\s{2,}", " ", s).strip()

    # Unicode ke ASCII
    s = unidecode(s).lower()

    # Hapus karakter non-alfanumerik kecuali spasi
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()

    return s


def normalize_artist(artist: str) -> str:
    """Normalisasi nama artis."""
    s = _FEAT_RE.sub("", artist)
    s = unidecode(s).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def normalize_artists(artists: list[str]) -> list[str]:
    return [normalize_artist(a) for a in artists]
