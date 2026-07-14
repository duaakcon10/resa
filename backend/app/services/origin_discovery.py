"""Origin IP Discovery — find the real IP behind CDN/WAF (Cloudflare, Vietnix, Akamai, etc.)
4 methods:
  1. Certificate Transparency logs (crt.sh)
  2. DNS history (SecurityTrails / ViewDNS API)
  3. Subdomain scan (direct DNS resolution bypass CDN)
  4. Common hosting IP probe (HTTP Host header injection)
"""
import asyncio
import aiohttp
import json
import socket
import ipaddress
from datetime import datetime, timezone
from typing import List, Optional


async def method_crt_logs(domain: str) -> List[dict]:
    """Method 1: Certificate Transparency — find IPs from SSL certs."""
    results = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(f"https://crt.sh/?q=%.{domain}&output=json") as r:
                if r.status == 200:
                    data = await r.json()
                    seen = set()
                    for entry in data[:500]:  # limit
                        name = entry.get("name_value", "")
                        for sub in name.split("\n"):
                            sub = sub.strip().lstrip("*.")
                            if sub and sub not in seen and domain in sub:
                                seen.add(sub)
                                try:
                                    ip = socket.gethostbyname(sub)
                                    results.append({
                                        "source": "crt.sh",
                                        "subdomain": sub,
                                        "ip": ip,
                                        "detail": f"CT log: {sub} → {ip}",
                                    })
                                except socket.gaierror:
                                    pass
    except Exception as e:
        results.append({"source": "crt.sh", "error": str(e)})
    return results


async def method_dns_history(domain: str) -> List[dict]:
    """Method 2: DNS history via ViewDNS.info (free, no API key)."""
    results = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            # ViewDNS IP history
            async with session.get(
                f"https://viewdns.info/iphistory/?domain={domain}",
                headers={"User-Agent": "Mozilla/5.0"},
            ) as r:
                if r.status == 200:
                    text = await r.text()
                    # Parse HTML table for IPs (simple regex)
                    import re
                    ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
                    seen = set()
                    for ip in ips:
                        if ip not in seen and not ip.startswith("0.") and not ip.startswith("127."):
                            seen.add(ip)
                            results.append({
                                "source": "dns_history",
                                "ip": ip,
                                "detail": f"DNS history: {domain} was {ip}",
                            })
    except Exception as e:
        results.append({"source": "dns_history", "error": str(e)})
    return results


async def method_subdomain_scan(domain: str) -> List[dict]:
    """Method 3: Scan common subdomains — some may resolve to origin IP directly."""
    results = []
    subdomains = [
        "www", "mail", "ftp", "cpanel", "webmail", "localhost", "direct",
        "origin", "backend", "api", "dev", "staging", "test", "beta",
        "ns1", "ns2", "smtp", "imap", "pop", "ssh", "vpn", "panel",
        "admin", "direct-connect", "server", "host", "real",
    ]
    try:
        loop = asyncio.get_event_loop()
        for sub in subdomains:
            full = f"{sub}.{domain}"
            try:
                ip = await loop.getaddrinfo(full, None, socket.AF_INET)
                if ip:
                    addr = ip[0][4][0]
                    # Check if this IP is NOT a known CDN range
                    if not _is_cdn_ip(addr):
                        results.append({
                            "source": "subdomain",
                            "subdomain": full,
                            "ip": addr,
                            "detail": f"Subdomain {full} → {addr} (non-CDN!)",
                        })
            except socket.gaierror:
                pass
    except Exception as e:
        results.append({"source": "subdomain", "error": str(e)})
    return results


async def method_host_probe(domain: str, candidate_ips: List[str]) -> List[dict]:
    """Method 4: Send HTTP with Host header to candidate IPs — check if server responds."""
    results = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            for ip in candidate_ips[:20]:  # limit probes
                try:
                    # Try both HTTP and HTTPS
                    for scheme in ["https", "http"]:
                        url = f"{scheme}://{ip}/"
                        try:
                            async with session.get(
                                url,
                                headers={"Host": domain, "User-Agent": "Mozilla/5.0"},
                                ssl=False,
                                allow_redirects=False,
                            ) as r:
                                server = r.headers.get("Server", "")
                                title = ""
                                if r.status in (200, 301, 302, 403):
                                    body = await r.text()
                                    import re
                                    m = re.search(r"<title>(.*?)</title>", body, re.I)
                                    if m:
                                        title = m.group(1)[:100]
                                    results.append({
                                        "source": "host_probe",
                                        "ip": ip,
                                        "scheme": scheme,
                                        "status": r.status,
                                        "server": server,
                                        "title": title,
                                        "detail": f"Host header probe {ip} → {r.status} {server} {title}",
                                    })
                                    break  # found response on this IP
                        except Exception:
                            continue
                except Exception:
                    continue
    except Exception as e:
        results.append({"source": "host_probe", "error": str(e)})
    return results


# Known CDN/WAF IP ranges (Cloudflare, Vietnix, Akamai, AWS)
CDN_RANGES = [
    # Cloudflare
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    # AWS CloudFront
    "13.32.0.0/15", "13.224.0.0/14", "52.46.0.0/18", "52.84.0.0/15",
    # Akamai
    "23.0.0.0/12", "72.246.0.0/13", "95.100.0.0/14",
    # Common Vietnix CDN ranges (approximate)
    "103.237.144.0/22", "103.237.148.0/22",
]


def _is_cdn_ip(ip_str: str) -> bool:
    """Check if IP is in known CDN range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in CDN_RANGES:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
    except ValueError:
        pass
    return False


async def discover_origin(domain: str) -> dict:
    """Run all 4 discovery methods in parallel, return consolidated results."""
    # Run all methods concurrently
    crt, dns, subs, _ = await asyncio.gather(
        method_crt_logs(domain),
        method_dns_history(domain),
        method_subdomain_scan(domain),
        asyncio.sleep(0),  # placeholder
    )

    # Collect unique non-CDN IPs for host probing
    candidate_ips = set()
    for method_results in [crt, dns, subs]:
        for r in method_results:
            if "ip" in r and not _is_cdn_ip(r["ip"]):
                candidate_ips.add(r["ip"])

    # Run host probe on candidates
    probe = await method_host_probe(domain, list(candidate_ips))

    # Consolidate
    all_results = crt + dns + subs + probe
    confirmed = [r for r in all_results if r.get("source") == "host_probe" and "ip" in r]
    likely = [r for r in all_results if r.get("ip") and not _is_cdn_ip(r["ip"]) and r.get("source") != "host_probe"]

    return {
        "domain": domain,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": len(all_results),
        "confirmed_origin_ips": [{"ip": r["ip"], "detail": r.get("detail", ""), "server": r.get("server", ""), "title": r.get("title", "")} for r in confirmed],
        "likely_origin_ips": [{"ip": r["ip"], "subdomain": r.get("subdomain", ""), "source": r.get("source", ""), "detail": r.get("detail", "")} for r in likely[:20]],
        "all_findings": all_results[:50],
        "cdn_detected": _is_cdn_ip(socket.gethostbyname(domain)) if _resolve(domain) else False,
    }


def _resolve(domain: str) -> bool:
    try:
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False
