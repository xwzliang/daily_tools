#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import browser_cookie3


BROWSER_LOADERS = {
    "chrome": browser_cookie3.chrome,
    "chromium": browser_cookie3.chromium,
    "brave": browser_cookie3.brave,
    "edge": browser_cookie3.edge,
    "firefox": browser_cookie3.firefox,
    "opera": browser_cookie3.opera,
    "vivaldi": browser_cookie3.vivaldi,
    "safari": browser_cookie3.safari,
}


def domain_matches(cookie_domain: str, hostname: str) -> bool:
    if not hostname:
        return False
    if cookie_domain.startswith("."):
        return hostname == cookie_domain[1:] or hostname.endswith(cookie_domain)
    return cookie_domain == hostname



def path_matches(cookie_path: str, request_path: str) -> bool:
    request_path = request_path or "/"
    cookie_path = cookie_path or "/"
    return request_path.startswith(cookie_path)



def cookie_matches_url(cookie, url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path or "/"

    if not domain_matches(cookie.domain, hostname):
        return False
    if not path_matches(cookie.path, path):
        return False
    if cookie.secure and parsed.scheme != "https":
        return False
    if cookie.expires is not None and cookie.expires < time.time():
        return False
    return True



def cookie_header_for_url(cj, url: str) -> str:
    cookies = [c for c in cj if cookie_matches_url(c, url)]
    cookies.sort(key=lambda c: len(c.path or "/"), reverse=True)
    return "; ".join(
        f"{c.name}={c.value}" if c.name else f"{c.value}" for c in cookies
    )



def cookie_dicts_for_url(cj, url: str) -> list[dict]:
    cookies = [c for c in cj if cookie_matches_url(c, url)]
    cookies.sort(key=lambda c: (len(c.path or "/"), c.name or ""), reverse=True)
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires,
            "discard": c.discard,
            "http_only": "HttpOnly" in getattr(c, "_rest", {}),
        }
        for c in cookies
    ]



def load_cookie_jar(browser: str, profile: Optional[str] = None):
    loader = BROWSER_LOADERS[browser]
    kwargs = {}
    if profile:
        kwargs["cookie_file"] = profile
    return loader(**kwargs)



def infer_url(raw: str) -> str:
    if "://" in raw:
        return raw
    return f"https://{raw}"



def write_text_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")



def write_json_output(path: Path, content: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")



def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract browser cookies for any website URL. Defaults to Chrome."
    )
    parser.add_argument(
        "url",
        help="Website URL or hostname, for example https://www.douyin.com/ or www.douyin.com",
    )
    parser.add_argument(
        "--browser",
        choices=sorted(BROWSER_LOADERS.keys()),
        default="chrome",
        help="Browser to read cookies from. Default: chrome",
    )
    parser.add_argument(
        "--profile",
        help="Optional browser cookie database path. Useful if auto-detection fails.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output matching cookies as JSON instead of a Cookie header string.",
    )
    parser.add_argument(
        "--output",
        help="Optional file path to write the result to.",
    )
    parser.add_argument(
        "--name",
        help="Only return a single cookie by name.",
    )
    return parser.parse_args(argv)



def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    url = infer_url(args.url)

    try:
        cj = load_cookie_jar(args.browser, args.profile)
    except Exception as exc:
        print(f"Failed to load cookies from {args.browser}: {exc}", file=sys.stderr)
        return 1

    cookies = cookie_dicts_for_url(cj, url)

    if args.name:
        cookies = [c for c in cookies if c["name"] == args.name]

    if not cookies:
        print(f"No matching cookies found for {url}", file=sys.stderr)
        return 2

    if args.json:
        output = json.dumps(cookies, ensure_ascii=False, indent=2)
    else:
        output = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c["name"])

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        if args.json:
            write_json_output(output_path, cookies)
        else:
            write_text_output(output_path, output)
        print(f"Wrote cookie output to {output_path}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
