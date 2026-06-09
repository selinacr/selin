"""Ortak HTTP katmanı: nazik başlıklar, zaman aşımı, üstel geri çekilmeli yeniden deneme.

Her tarama kaynakları sıfırdan sorgular (önbellek yok) — kullanıcının istediği
"her seferinde güncel" davranışı için tasarımın temel kuralıdır.
"""

from __future__ import annotations

import time

import requests

DEFAULT_TIMEOUT = 30
CONTACT_EMAIL = "ardes@dogus.edu.tr"
USER_AGENT = (
    f"litera-tarama/1.0 (akademik literatur tarama araci; mailto:{CONTACT_EMAIL})"
)


class HttpError(Exception):
    """Tüm yeniden denemeler tükendiğinde fırlatılır."""


_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session = s
    return _session


def _request(url: str, params, timeout, retries, headers):
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session().get(url, params=params, timeout=timeout, headers=headers)
            if resp.status_code == 429:  # hız sınırı — bekle ve tekrar dene
                wait = 2 ** attempt + 1
                last_err = HttpError(f"429 hız sınırı: {url}")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(min(2 ** attempt, 8))
    raise HttpError(f"İstek başarısız ({url}): {last_err}")


def get_json(url, params=None, *, timeout=DEFAULT_TIMEOUT, retries=3, headers=None):
    return _request(url, params, timeout, retries, headers).json()


def get_text(url, params=None, *, timeout=DEFAULT_TIMEOUT, retries=3, headers=None):
    return _request(url, params, timeout, retries, headers).text
