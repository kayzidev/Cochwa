"""Sessions par thread, limites de temps et reprises bornées."""

import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_local = threading.local()


def session():
    if not hasattr(_local, "session"):
        client = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            respect_retry_after_header=False,
        )
        client.mount("https://", HTTPAdapter(max_retries=retry))
        client.mount("http://", HTTPAdapter(max_retries=retry))
        client.headers["User-Agent"] = "romget/0.2"
        _local.session = client
    return _local.session


def get_json(url, **kwargs):
    import json

    body = bytearray()
    with session().get(url, timeout=(10, 25), stream=True, **kwargs) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 16 * 1024**2:
                raise ValueError("Réponse JSON trop volumineuse")
    return json.loads(body)
