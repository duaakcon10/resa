"""Origin IP Discovery behind Cloudflare / Vietnix / Akamai (CloudFail-style).

CF proxy only hides A/AAAA of the apex domain. Origin often leaks via:
  1. Crimeflare / historical CF leak DBs
  2. Misconfigured DNS (MX, NS, FTP, mail, direct subdomains not orange-clouded)
  3. Subdomain bruteforce (resolve + not-in-CF-range)
  4. Certificate Transparency (crt.sh) → subdomains → resolve
  5. DNS history (ViewDNS / free APIs)
  6. Host-header probe (confirm IP serves the site)

If CF is configured perfectly (no mail/sub/history leak), origin may be unfindable.
"""
import asyncio
import aiohttp
import re
import socket
import ipaddress
from datetime import datetime, timezone
from typing import List, Set, Optional

# Cloudflare IPv4 ranges (subset + common — refresh from https://www.cloudflare.com/ips-v4)
CF_RANGES = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22", "104.16.0.0/12",
]
# Other CDNs / edges
CDN_RANGES = CF_RANGES + [
    "13.32.0.0/15", "13.224.0.0/14", "52.46.0.0/18", "52.84.0.0/15",
    "23.0.0.0/12", "72.246.0.0/13", "95.100.0.0/14",
    "103.237.144.0/22", "103.237.148.0/22",
]

# CloudFail-style subdomains (high-yield first)
SUBDOMAINS = [
    "www", "mail", "ftp", "cpanel", "webmail", "direct", "origin", "backend",
    "api", "dev", "staging", "test", "beta", "ns1", "ns2", "smtp", "imap", "pop",
    "ssh", "vpn", "panel", "admin", "server", "host", "cdn", "static", "img",
    "images", "assets", "media", "blog", "shop", "store", "app", "m", "mobile",
    "portal", "secure", "vpn", "remote", "git", "gitlab", "jenkins", "ci",
    "db", "mysql", "postgres", "redis", "elastic", "kibana", "grafana",
    "autodiscover", "owa", "exchange", "webdisk", "whm", "webmail2",
    "old", "legacy", "backup", "bak", "new", "v2", "v1", "demo", "sandbox",
    "status", "monitor", "mx", "mx1", "mx2", "email", "mail1", "mail2",
    "cpanel", "cpcalendars", "cpcontacts", "webmail", "direct-connect",
    "origin-www", "www-origin", "cf-origin", "real", "ip", "bare",
    "n8n", "portainer", "traefik", "proxy", "gateway", "lb",
]


def _is_cdn_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in CDN_RANGES:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
    except ValueError:
        pass
    return False


def _resolve_sync(host: str) -> Optional[str]:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


async def _resolve(host: str) -> Optional[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _resolve_sync, host)


async def method_crimeflare(domain: str) -> List[dict]:
    """Crimeflare / CF leak DB (CloudFail phase 2) — historical origin IPs."""
    results = []
    urls = [
        "https://cf.ozeliurs.com/ipout",
        "https://raw.githubusercontent.com/m0rtem/CloudFail/master/data/ipout",
    ]
    domain_l = domain.lower().strip(".")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            for url in urls:
                try:
                    async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
                        if r.status != 200:
                            continue
                        text = await r.text()
                        for line in text.splitlines():
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                # formats vary: id domain ip  OR  domain ip
                                d, ip = None, None
                                for p in parts:
                                    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", p):
                                        ip = p
                                    elif domain_l in p.lower() or p.lower().endswith(domain_l):
                                        d = p.lower()
                                if ip and (d is None or domain_l in d or d == domain_l):
                                    # line often: <id> <domain> <ip>
                                    if len(parts) >= 3 and parts[1].lower().rstrip(".") == domain_l:
                                        ip = parts[2].strip()
                                        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) and not _is_cdn_ip(ip):
                                            results.append({
                                                "source": "crimeflare",
                                                "ip": ip,
                                                "detail": f"Crimeflare DB: {domain} → {ip}",
                                            })
                        if results:
                            break
                except Exception:
                    continue
    except Exception as e:
        results.append({"source": "crimeflare", "error": str(e)})
    # dedupe
    seen = set()
    out = []
    for r in results:
        ip = r.get("ip")
        if ip and ip not in seen:
            seen.add(ip)
            out.append(r)
    return out


async def method_mx_ns(domain: str) -> List[dict]:
    """MX / NS / TXT often point outside Cloudflare orange cloud."""
    results = []
    loop = asyncio.get_event_loop()

    def _dns(name, rtype):
        try:
            import dns.resolver
            ans = dns.resolver.resolve(name, rtype)
            return [str(r) for r in ans]
        except Exception:
            # fallback: no dnspython — use socket for A only
            return []

    try:
        for rtype in ("MX", "NS", "A", "AAAA"):
            try:
                recs = await loop.run_in_executor(None, _dns, domain, rtype)
            except Exception:
                recs = []
            for rec in recs:
                host = rec.split()[-1].rstrip(".") if rtype == "MX" else rec.rstrip(".")
                if rtype in ("A", "AAAA"):
                    ip = host if re.match(r"^\d", host) else await _resolve(host)
                else:
                    ip = await _resolve(host)
                if ip and not _is_cdn_ip(ip):
                    results.append({
                        "source": f"dns_{rtype.lower()}",
                        "subdomain": host if rtype != "A" else domain,
                        "ip": ip,
                        "detail": f"{rtype} {host} → {ip} (not CF range)",
                    })
    except Exception as e:
        results.append({"source": "dns_mx_ns", "error": str(e)})

    # Always try mail.* and direct A via system resolver
    for sub in ("mail", "smtp", "ftp", "direct", "cpanel", "webmail"):
        full = f"{sub}.{domain}"
        ip = await _resolve(full)
        if ip and not _is_cdn_ip(ip):
            results.append({
                "source": "dns_common",
                "subdomain": full,
                "ip": ip,
                "detail": f"{full} → {ip} (not CF)",
            })
    return results


async def method_crt_logs(domain: str) -> List[dict]:
    results = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(
                f"https://crt.sh/?q=%25.{domain}&output=json",
                headers={"User-Agent": "Mozilla/5.0"},
            ) as r:
                if r.status != 200:
                    return results
                data = await r.json(content_type=None)
                seen: Set[str] = set()
                for entry in data[:800]:
                    name = entry.get("name_value", "")
                    for sub in name.split("\n"):
                        sub = sub.strip().lstrip("*.")
                        if not sub or sub in seen or domain not in sub:
                            continue
                        seen.add(sub)
                        ip = await _resolve(sub)
                        if ip and not _is_cdn_ip(ip):
                            results.append({
                                "source": "crt.sh",
                                "subdomain": sub,
                                "ip": ip,
                                "detail": f"CT: {sub} → {ip}",
                            })
    except Exception as e:
        results.append({"source": "crt.sh", "error": str(e)})
    return results


async def method_dns_history(domain: str) -> List[dict]:
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            # ViewDNS
            async with session.get(
                f"https://viewdns.info/iphistory/?domain={domain}",
                headers=headers,
            ) as r:
                if r.status == 200:
                    text = await r.text()
                    for ip in re.findall(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", text):
                        if not _is_cdn_ip(ip) and not ip.startswith(("0.", "127.")):
                            results.append({
                                "source": "viewdns",
                                "ip": ip,
                                "detail": f"ViewDNS history: {domain} was {ip}",
                            })
            # HackerTarget hostsearch (often free, rate-limited)
            try:
                async with session.get(
                    f"https://api.hackertarget.com/hostsearch/?q={domain}",
                    headers=headers,
                ) as r2:
                    if r2.status == 200:
                        text = await r2.text()
                        if "error" not in text.lower() and "api count" not in text.lower():
                            for line in text.splitlines():
                                parts = line.strip().split(",")
                                if len(parts) >= 2:
                                    sub, ip = parts[0], parts[1]
                                    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) and not _is_cdn_ip(ip):
                                        results.append({
                                            "source": "hackertarget",
                                            "subdomain": sub,
                                            "ip": ip,
                                            "detail": f"HackerTarget: {sub} → {ip}",
                                        })
            except Exception:
                pass
    except Exception as e:
        results.append({"source": "dns_history", "error": str(e)})
    # dedupe
    seen = set()
    out = []
    for r in results:
        k = r.get("ip")
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return out


async def method_subdomain_scan(domain: str) -> List[dict]:
    """CloudFail phase 3: resolve many subdomains; keep non-CDN IPs."""
    results = []
    # parallel resolve in batches
    batch = 40
    for i in range(0, len(SUBDOMAINS), batch):
        chunk = SUBDOMAINS[i : i + batch]
        tasks = [_resolve(f"{s}.{domain}") for s in chunk]
        ips = await asyncio.gather(*tasks)
        for s, ip in zip(chunk, ips):
            if ip and not _is_cdn_ip(ip):
                results.append({
                    "source": "subdomain_bruteforce",
                    "subdomain": f"{s}.{domain}",
                    "ip": ip,
                    "detail": f"{s}.{domain} → {ip} (not CF range)",
                })
    return results


async def method_host_probe(domain: str, candidate_ips: List[str]) -> List[dict]:
    """Confirm IP serves the site via Host header (CloudFail-style validation)."""
    results = []
    if not candidate_ips:
        return results
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            for ip in candidate_ips[:25]:
                for scheme in ("https", "http"):
                    try:
                        async with session.get(
                            f"{scheme}://{ip}/",
                            headers={"Host": domain, "User-Agent": "Mozilla/5.0"},
                            ssl=False,
                            allow_redirects=False,
                        ) as r:
                            if r.status not in (200, 301, 302, 401, 403, 404):
                                continue
                            body = await r.text()
                            title_m = re.search(r"<title>(.*?)</title>", body, re.I | re.S)
                            title = (title_m.group(1)[:80].strip() if title_m else "")
                            server = r.headers.get("Server", "")
                            # Prefer non-CF server headers
                            if "cloudflare" in server.lower() or "cf-ray" in {k.lower() for k in r.headers}:
                                continue
                            results.append({
                                "source": "host_probe",
                                "ip": ip,
                                "scheme": scheme,
                                "status": r.status,
                                "server": server,
                                "title": title,
                                "detail": f"Host probe {ip} → HTTP {r.status} {server} {title}",
                            })
                            break
                    except Exception:
                        continue
    except Exception as e:
        results.append({"source": "host_probe", "error": str(e)})
    return results


async def discover_origin(domain: str) -> dict:
    """Full CloudFail-style pipeline."""
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]

    apex_ip = await _resolve(domain)
    on_cf = bool(apex_ip and _is_cdn_ip(apex_ip))

    crime, mx, crt, hist, subs = await asyncio.gather(
        method_crimeflare(domain),
        method_mx_ns(domain),
        method_crt_logs(domain),
        method_dns_history(domain),
        method_subdomain_scan(domain),
    )

    candidates: List[str] = []
    seen: Set[str] = set()
    for block in (crime, mx, crt, hist, subs):
        for r in block:
            ip = r.get("ip")
            if ip and ip not in seen and not _is_cdn_ip(ip):
                seen.add(ip)
                candidates.append(ip)

    probe = await method_host_probe(domain, candidates)
    all_results = crime + mx + crt + hist + subs + probe
    confirmed = [r for r in probe if r.get("ip")]
    likely = [
        {"ip": r["ip"], "subdomain": r.get("subdomain", ""), "source": r.get("source", ""), "detail": r.get("detail", "")}
        for r in all_results
        if r.get("ip") and not _is_cdn_ip(r["ip"]) and r.get("source") != "host_probe"
    ]
    # dedupe likely
    seen_l = set()
    likely_u = []
    for r in likely:
        if r["ip"] not in seen_l:
            seen_l.add(r["ip"])
            likely_u.append(r)

    return {
        "domain": domain,
        "apex_ip": apex_ip,
        "cdn_detected": on_cf,
        "cdn_type": "cloudflare" if on_cf else ("cdn" if apex_ip and _is_cdn_ip(apex_ip) else "none"),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": len(all_results),
        "confirmed_origin_ips": [
            {
                "ip": r["ip"],
                "detail": r.get("detail", ""),
                "server": r.get("server", ""),
                "title": r.get("title", ""),
                "status": r.get("status"),
            }
            for r in confirmed
        ],
        "likely_origin_ips": likely_u[:30],
        "methods_used": [
            "crimeflare", "mx_ns", "crt.sh", "dns_history", "subdomain_bruteforce", "host_probe",
        ],
        "note": (
            "CF proxy only hides the main A record. Origin often leaks via mail/MX, "
            "subdomains not on CF, Crimeflare history, or old DNS. "
            "If empty: origin may be fully locked (no public leak)."
            if on_cf else "Domain may not be on Cloudflare — apex IP might already be origin."
        ),
        "all_findings": all_results[:80],
    }
