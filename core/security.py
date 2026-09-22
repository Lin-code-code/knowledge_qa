"""API Key 鉴权依赖。"""
import hmac

from fastapi import Header, HTTPException, status

from core.config import env_conf


def _configured_keys() -> list[str]:
    """解析 API_KEYS（逗号分隔），忽略空项。"""
    return [k.strip() for k in env_conf.API_KEYS.split(",") if k.strip()]


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    校验 X-API-Key 请求头。

    未配置 API_KEYS 时放行（本地开发/存量部署向后兼容）；
    配置后缺失或错误的 key 一律返回 401。
    """
    keys = _configured_keys()
    if not keys:
        return
    if not x_api_key or not any(hmac.compare_digest(x_api_key, k) for k in keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失的 API Key",
            headers={"WWW-Authenticate": "API-Key"},
        )
