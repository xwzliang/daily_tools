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

DEFAULT_CHROME_COOKIE_FILE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Google"
    / "Chrome"
    / "Profile 1"
    / "Cookies"
)


def normalize_cookie_domain(cookie_domain: str) -> str:
    return (cookie_domain or "").lstrip(".").lower()


def domain_matches(cookie_domain: str, hostname: str) -> bool:
    host = (hostname or "").lower()
    cdomain = normalize_cookie_domain(cookie_domain)

    if not host or not cdomain:
        return False

    return host == cdomain or host.endswith("." + cdomain)


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
    return "; ".join(f"{c.name}={c.value}" if c.name else f"{c.value}" for c in cookies)


def cookie_dict_from_cookie(c) -> dict:
    rest = getattr(c, "_rest", {}) or {}
    http_only = any(str(k).lower() == "httponly" for k in rest.keys())
    same_site = None
    for k, v in rest.items():
        if str(k).lower() == "samesite":
            same_site = v
            break

    return {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path,
        "secure": c.secure,
        "expires": c.expires,
        "discard": c.discard,
        "http_only": http_only,
        "same_site": same_site,
    }


def cookie_dicts_for_url(cj, url: str) -> list[dict]:
    cookies = [c for c in cj if cookie_matches_url(c, url)]
    cookies.sort(key=lambda c: (len(c.path or "/"), c.name or ""), reverse=True)
    return [cookie_dict_from_cookie(c) for c in cookies]


def infer_url(raw: str) -> str:
    if "://" in raw:
        return raw
    return f"https://{raw}"


def base_domain_for_filter(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    parts = hostname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def write_text_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_output(path: Path, content: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_profile(browser: str, profile: Optional[str]) -> Optional[str]:
    if profile:
        return str(Path(profile).expanduser().resolve())

    if browser == "chrome":
        return str(DEFAULT_CHROME_COOKIE_FILE)

    return None


def load_cookie_jar(browser: str, url: str, profile: Optional[str] = None):
    loader = BROWSER_LOADERS[browser]
    kwargs = {}

    domain_name = base_domain_for_filter(url)
    if domain_name:
        kwargs["domain_name"] = domain_name

    resolved_profile = resolve_profile(browser, profile)
    if resolved_profile:
        kwargs["cookie_file"] = resolved_profile

    return loader(**kwargs)


def debug_print_cookie(cookie, target_url: str, max_value_len: int = 80) -> None:
    parsed = urlparse(target_url)
    hostname = parsed.hostname or ""
    path = parsed.path or "/"
    now = time.time()

    domain_ok = domain_matches(cookie.domain, hostname)
    path_ok = path_matches(cookie.path, path)
    secure_ok = not cookie.secure or parsed.scheme == "https"
    not_expired = cookie.expires is None or cookie.expires >= now
    overall = domain_ok and path_ok and secure_ok and not_expired

    value_preview = cookie.value
    if value_preview is None:
        value_preview = ""
    if len(value_preview) > max_value_len:
        value_preview = value_preview[:max_value_len] + "...<truncated>"

    expires_str = "session"
    if cookie.expires is not None:
        expires_str = f"{cookie.expires} ({int(cookie.expires - now)}s from now)"

    print(
        f"[COOKIE] name={cookie.name!r} "
        f"domain={cookie.domain!r} "
        f"path={cookie.path!r} "
        f"secure={cookie.secure} "
        f"expires={expires_str} "
        f"match_domain={domain_ok} "
        f"match_path={path_ok} "
        f"match_secure={secure_ok} "
        f"match_expiry={not_expired} "
        f"overall_match={overall}",
        file=sys.stderr,
    )
    print(f"         value_preview={value_preview!r}", file=sys.stderr)


def debug_scan_cookie_jar(cj, url: str, limit: int = 200) -> None:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    base_domain = base_domain_for_filter(url)
    host_suffixes = []
    if hostname:
        parts = hostname.split(".")
        for i in range(len(parts)):
            host_suffixes.append(".".join(parts[i:]))

    all_cookies = list(cj)

    print("=== DEBUG SCAN START ===", file=sys.stderr)
    print(f"Target URL: {url}", file=sys.stderr)
    print(f"Target hostname: {hostname}", file=sys.stderr)
    print(f"Base domain filter guess: {base_domain}", file=sys.stderr)
    print(f"Hostname suffixes: {host_suffixes}", file=sys.stderr)
    print(f"Cookie jar total count: {len(all_cookies)}", file=sys.stderr)

    if not all_cookies:
        print("Cookie jar is empty after loader returned.", file=sys.stderr)
        print("=== DEBUG SCAN END ===", file=sys.stderr)
        return

    domain_hits = []
    partial_hits = []

    for c in all_cookies:
        cdomain = normalize_cookie_domain(c.domain)
        if cdomain == hostname or hostname.endswith("." + cdomain):
            domain_hits.append(c)
        elif any(
            sfx == cdomain or sfx.endswith("." + cdomain) for sfx in host_suffixes
        ):
            partial_hits.append(c)
        elif base_domain and (
            cdomain == base_domain
            or cdomain.endswith("." + base_domain)
            or base_domain.endswith("." + cdomain)
        ):
            partial_hits.append(c)

    unique_domains = sorted({(c.domain or "") for c in all_cookies})
    preview_domains = unique_domains[:100]

    print(f"Unique cookie domains found: {len(unique_domains)}", file=sys.stderr)
    print("First 100 domains:", file=sys.stderr)
    for d in preview_domains:
        print(f"  - {d!r}", file=sys.stderr)

    print(
        f"Direct/relevant domain-hit cookie count: {len(domain_hits)}", file=sys.stderr
    )
    print(f"Partial-hit cookie count: {len(partial_hits)}", file=sys.stderr)

    if domain_hits:
        print("Showing direct/relevant domain-hit cookies:", file=sys.stderr)
        for c in domain_hits[:limit]:
            debug_print_cookie(c, url)

    elif partial_hits:
        print("No direct domain hits. Showing partial-hit cookies:", file=sys.stderr)
        for c in partial_hits[:limit]:
            debug_print_cookie(c, url)

    else:
        print("No related domains found in loaded cookie jar.", file=sys.stderr)
        print("Showing first cookies from jar for inspection:", file=sys.stderr)
        for c in all_cookies[: min(limit, 50)]:
            debug_print_cookie(c, url)

    print("=== DEBUG SCAN END ===", file=sys.stderr)


def try_load_cookie_jar_variants(
    browser: str,
    url: str,
    profile: Optional[str] = None,
    debug: bool = False,
):
    loader = BROWSER_LOADERS[browser]
    base_domain = base_domain_for_filter(url)
    resolved_profile = resolve_profile(browser, profile)

    attempts = []

    if base_domain:
        kwargs = {"domain_name": base_domain}
        if resolved_profile:
            kwargs["cookie_file"] = resolved_profile
        attempts.append(("with base domain filter", kwargs))

    hostname = urlparse(url).hostname or ""
    if hostname and hostname != base_domain:
        kwargs = {"domain_name": hostname}
        if resolved_profile:
            kwargs["cookie_file"] = resolved_profile
        attempts.append(("with full hostname filter", kwargs))

    kwargs = {}
    if resolved_profile:
        kwargs["cookie_file"] = resolved_profile
    attempts.append(("without domain filter", kwargs))

    errors = []

    for label, kwargs in attempts:
        try:
            if debug:
                print(
                    f"Trying loader for browser={browser!r} {label}: kwargs={kwargs}",
                    file=sys.stderr,
                )
            cj = loader(**kwargs)
            cookies = list(cj)
            if debug:
                print(
                    f"Loader succeeded {label}, cookie count={len(cookies)}",
                    file=sys.stderr,
                )
            return cookies, label, resolved_profile, None
        except Exception as exc:
            errors.append((label, exc))
            if debug:
                print(f"Loader failed {label}: {exc}", file=sys.stderr)

    return None, None, resolved_profile, errors


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed debug information to stderr.",
    )
    parser.add_argument(
        "--debug-limit",
        type=int,
        default=200,
        help="Maximum number of cookies to print in debug scan. Default: 200",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    url = infer_url(args.url)
    resolved_profile = resolve_profile(args.browser, args.profile)

    if args.debug:
        print("=== BASIC DEBUG INFO ===", file=sys.stderr)
        print(f"Input URL: {args.url}", file=sys.stderr)
        print(f"Normalized URL: {url}", file=sys.stderr)
        print(f"Browser: {args.browser}", file=sys.stderr)
        print(f"Profile arg: {args.profile!r}", file=sys.stderr)
        print(f"Resolved profile: {resolved_profile!r}", file=sys.stderr)
        print(f"Base domain: {base_domain_for_filter(url)!r}", file=sys.stderr)
        print(f"Hostname: {(urlparse(url).hostname or '')!r}", file=sys.stderr)
        print(f"Path: {(urlparse(url).path or '/')!r}", file=sys.stderr)
        if resolved_profile:
            rp = Path(resolved_profile).expanduser()
            print(f"Resolved profile exists: {rp.exists()}", file=sys.stderr)
            print(f"Resolved profile is_file: {rp.is_file()}", file=sys.stderr)
        print("========================", file=sys.stderr)

    cookies_list, load_mode, resolved_profile, load_errors = (
        try_load_cookie_jar_variants(
            args.browser,
            url,
            args.profile,
            args.debug,
        )
    )

    if cookies_list is None:
        print(f"Failed to load cookies from {args.browser}", file=sys.stderr)
        if load_errors:
            for label, exc in load_errors:
                print(f"  - {label}: {exc}", file=sys.stderr)
        return 1

    if args.debug:
        print(f"Chosen load mode: {load_mode}", file=sys.stderr)
        print(f"Chosen resolved profile: {resolved_profile!r}", file=sys.stderr)

    cj = cookies_list

    if args.debug:
        debug_scan_cookie_jar(cj, url, limit=args.debug_limit)

    cookies = cookie_dicts_for_url(cj, url)

    if args.name:
        before = len(cookies)
        cookies = [c for c in cookies if c["name"] == args.name]
        if args.debug:
            print(
                f"Applied --name filter {args.name!r}: {before} -> {len(cookies)}",
                file=sys.stderr,
            )

    if args.debug:
        print(f"Final matched cookie count: {len(cookies)}", file=sys.stderr)
        if cookies:
            print("Final matched cookies:", file=sys.stderr)
            for c in cookies:
                print(
                    f"  - {c['name']!r} domain={c['domain']!r} path={c['path']!r} secure={c['secure']}",
                    file=sys.stderr,
                )

    if not cookies:
        print(f"No matching cookies found for {url}", file=sys.stderr)
        print(
            "Tips: make sure that website is actually logged in in this browser/profile.",
            file=sys.stderr,
        )
        if args.browser == "chrome":
            print(
                f"Current default Chrome cookie file is: {DEFAULT_CHROME_COOKIE_FILE}",
                file=sys.stderr,
            )
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
