"""Security helpers for validating and embedding YouTube trailers."""

from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError


ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

VALID_VIDEO_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


def extract_youtube_video_id(raw_url: str) -> str | None:
    if not isinstance(raw_url, str):
        return None

    cleaned = raw_url[:2048].strip()
    if not cleaned:
        return None

    try:
        parsed = urlparse(cleaned)
    except Exception:
        return None

    if parsed.scheme != "https":
        return None

    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return None

    video_id = None
    path_parts = [p for p in parsed.path.split("/") if p]

    if "youtu.be" in host:
        if path_parts:
            video_id = path_parts[0]
    elif parsed.path == "/watch":
        qs = parse_qs(parsed.query)
        video_id = (qs.get("v") or [None])[0]
    else:
        if "embed" in path_parts:
            idx = path_parts.index("embed")
            if idx + 1 < len(path_parts):
                video_id = path_parts[idx + 1]
        elif "shorts" in path_parts:
            idx = path_parts.index("shorts")
            if idx + 1 < len(path_parts):
                video_id = path_parts[idx + 1]

    if not video_id or len(video_id) != 11:
        return None

    if any(ch not in VALID_VIDEO_CHARS for ch in video_id):
        return None

    return video_id


def validate_youtube_trailer_url(value: str) -> None:
    if not value:
        return
    if extract_youtube_video_id(value) is None:
        raise ValidationError("Enter a valid HTTPS YouTube trailer URL.")


def build_safe_embed_url(video_id: str, autoplay: bool = False) -> str:
    auto = "1" if autoplay else "0"
    return (
        f"https://www.youtube.com/embed/{video_id}"
        f"?rel=0&modestbranding=1&playsinline=1&autoplay={auto}"
    )


def build_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
