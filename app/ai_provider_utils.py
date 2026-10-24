"""Shared validation and endpoint helpers for official and relay AI APIs."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import requests


DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
}


def normalize_base_url(value: str, provider: str) -> str:
    value = (value or "").strip() or DEFAULT_BASE_URLS[provider]
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("API URL 必须是有效的 HTTP(S) 地址")
    if parsed.username or parsed.password:
        raise ValueError("API URL 不能包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("API URL 不能包含查询参数或片段")
    hostname = parsed.hostname.lower().rstrip(".")
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port:
        netloc += f":{parsed.port}"
    path = (parsed.path or "").rstrip("/")
    return urlunsplit((parsed.scheme, netloc, path, "", ""))


def validate_public_base_url(value: str, provider: str) -> str:
    normalized = normalize_base_url(value, provider)
    hostname = urlsplit(normalized).hostname
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError("API URL 域名无法解析") from exc
    if not addresses:
        raise ValueError("API URL 域名无法解析")
    for address in addresses:
        try:
            ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("API URL 解析结果无效") from exc
    return normalized


def endpoint_url(base_url: str, suffix: str) -> str:
    base = base_url.rstrip("/")
    suffix = "/" + suffix.strip("/")
    return base if base.endswith(suffix) else base + suffix


def models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/messages"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break
    return endpoint_url(base, "models")


def auth_headers(provider: str, api_key: str) -> dict[str, str]:
    if provider == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def fetch_models(provider: str, api_key: str, base_url: str) -> list[str]:
    if not api_key:
        raise ValueError("请先填写或保存 API Key")
    safe_base = validate_public_base_url(base_url, provider)
    response = requests.get(
        models_url(safe_base),
        headers=auth_headers(provider, api_key),
        timeout=30,
        allow_redirects=False,
    )
    if not response.ok:
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            detail = error.get("message") if isinstance(error, dict) else error
        except Exception:
            detail = response.text
        raise RuntimeError(str(detail or f"HTTP {response.status_code}")[:500])
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError("模型接口返回格式不兼容")
    models = sorted({
        str(item.get("id") or "").strip()
        for item in data if isinstance(item, dict) and item.get("id")
    })
    if not models:
        raise RuntimeError("服务商未返回可用模型")
    return models
