from __future__ import annotations

import traceback
import secrets
import json
import base64

from quart import Blueprint, jsonify, request, current_app
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash
import aiohttp

from src.core.audit import new_trace_id
from src.infra.database.mysql import async_mysql_pool, AuthUser
from src.infra.shared.jwt import create_token


def _oauth_cfg(provider: str) -> dict:
    p = provider.upper()
    return {
        "provider": provider,
        "client_id": (current_app.config.get(f"{p}_CLIENT_ID") or "").strip(),
        "client_secret": (current_app.config.get(f"{p}_CLIENT_SECRET") or "").strip(),
        "auth_url": (current_app.config.get(f"{p}_AUTH_URL") or "").strip(),
        "token_url": (current_app.config.get(f"{p}_TOKEN_URL") or "").strip(),
        "userinfo_url": (current_app.config.get(f"{p}_USERINFO_URL") or "").strip(),
        "scope": (current_app.config.get(f"{p}_SCOPE") or "").strip(),
    }


def _extract_oauth_identity(provider: str, token_payload: dict, userinfo: dict | None) -> tuple[str, str]:
    def _decode_id_token(jwt_token: str) -> dict:
        try:
            parts = (jwt_token or "").split(".")
            if len(parts) < 2:
                return {}
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return {}

    info = userinfo or {}
    id_token_claims = _decode_id_token((token_payload or {}).get("id_token") or "")
    if provider == "google":
        sub = (info.get("sub") or id_token_claims.get("sub") or "").strip()
        email = (info.get("email") or id_token_claims.get("email") or "").strip()
        return sub, email
    if provider == "apple":
        # Apple 常见场景下 only returns id_token，userinfo 可能为空。
        sub = (info.get("sub") or id_token_claims.get("sub") or "").strip()
        email = (info.get("email") or id_token_claims.get("email") or "").strip()
        return sub, email
    return "", ""


def create_auth_bp() -> Blueprint:
    """
    简单登录接口：前端提交 user_id，后端签发 JWT。

    Body:
    {
        "user_id": "user_001"
    }

    返回:
    {
        "user_id": "user_001",
        "token": "<jwt>",
        "expires_in": 604800   # 秒
    }
    """
    auth_bp = Blueprint("auth", __name__, url_prefix="/v1/api")

    @auth_bp.route("/login", methods=["POST"])
    async def login():
        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        try:
            data = await request.get_json() or {}
            user_id = (data.get("user_id") or "").strip()
            password = (data.get("password") or "").strip()
            if not user_id:
                return jsonify({"error": "user_id is required", "trace_id": trace_id}), 400
            if not password:
                return jsonify({"error": "password is required", "trace_id": trace_id}), 400

            async with async_mysql_pool.session() as session:
                result = await session.execute(
                    select(AuthUser).where(AuthUser.user_id == user_id).limit(1)
                )
                user = result.scalars().one_or_none()
            if user is None:
                return jsonify({"error": "user not found", "trace_id": trace_id}), 404
            if not user.is_active:
                return jsonify({"error": "user is disabled", "trace_id": trace_id}), 403
            if not check_password_hash(user.password_hash, password):
                return jsonify({"error": "invalid credentials", "trace_id": trace_id}), 401

            token = create_token(user_id)
            # 从应用配置里读取过期时间，方便前端展示
            expires_in = int(current_app.config.get("JWT_EXPIRE_SECONDS", 7 * 24 * 3600))

            return (
                jsonify(
                    {
                        "user_id": user_id,
                        "token": token,
                        "token_type": "Bearer",
                        "expires_in": expires_in,
                        "trace_id": trace_id,
                    }
                ),
                200,
            )
        except Exception as e:
            tb = traceback.format_exc()
            current_app.logger.exception("Unhandled error in /login (trace_id=%s)", trace_id)
            return jsonify(
                {
                    "error": str(e),
                    "trace_id": trace_id,
                    "traceback": tb,
                }
            ), 500

    @auth_bp.route("/register", methods=["POST"])
    async def register():
        """
        注册接口：创建账号并签发 JWT。
        """
        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        try:
            data = await request.get_json() or {}
            user_id = (data.get("user_id") or "").strip()
            password = (data.get("password") or "").strip()
            if not user_id:
                return jsonify({"error": "user_id is required", "trace_id": trace_id}), 400
            if len(user_id) < 3:
                return jsonify({"error": "user_id must be at least 3 characters", "trace_id": trace_id}), 400
            if not password:
                return jsonify({"error": "password is required", "trace_id": trace_id}), 400
            if len(password) < 6:
                return jsonify({"error": "password must be at least 6 characters", "trace_id": trace_id}), 400

            async with async_mysql_pool.session() as session:
                existed = await session.execute(
                    select(AuthUser.user_id).where(AuthUser.user_id == user_id).limit(1)
                )
                existed_user_id = existed.scalars().first()
                if existed_user_id is not None:
                    return (
                        jsonify(
                            {
                                "error": "user_id already exists in auth_users",
                                "trace_id": trace_id,
                                "conflict_user_id": existed_user_id,
                            }
                        ),
                        409,
                    )

                user = AuthUser(
                    user_id=user_id,
                    password_hash=generate_password_hash(password),
                    is_active=True,
                )
                session.add(user)
                await session.commit()

            token = create_token(user_id)
            expires_in = int(current_app.config.get("JWT_EXPIRE_SECONDS", 7 * 24 * 3600))
            return (
                jsonify(
                    {
                        "user_id": user_id,
                        "token": token,
                        "token_type": "Bearer",
                        "expires_in": expires_in,
                        "trace_id": trace_id,
                    }
                ),
                200,
            )
        except Exception as e:
            tb = traceback.format_exc()
            current_app.logger.exception("Unhandled error in /register (trace_id=%s)", trace_id)
            return jsonify(
                {
                    "error": str(e),
                    "trace_id": trace_id,
                    "traceback": tb,
                }
            ), 500

    @auth_bp.route("/oauth/start", methods=["POST"])
    async def oauth_start():
        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        try:
            body = await request.get_json() or {}
            provider = (body.get("provider") or "").strip().lower()
            redirect_uri = (body.get("redirect_uri") or "").strip()
            if provider not in {"google", "apple"}:
                return jsonify({"error": "unsupported provider", "trace_id": trace_id}), 400
            if not redirect_uri:
                return jsonify({"error": "redirect_uri is required", "trace_id": trace_id}), 400

            cfg = _oauth_cfg(provider)
            if not cfg["client_id"] or not cfg["auth_url"]:
                return (
                    jsonify(
                        {
                            "error": f"{provider} oauth is not configured",
                            "trace_id": trace_id,
                            "missing": ["CLIENT_ID or AUTH_URL"],
                        }
                    ),
                    501,
                )

            state = secrets.token_urlsafe(24)
            nonce = secrets.token_urlsafe(24)
            params = {
                "client_id": cfg["client_id"],
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": cfg["scope"] or "openid email profile",
                "state": state,
                "nonce": nonce,
            }
            if provider == "apple":
                params["response_mode"] = "query"

            from urllib.parse import urlencode

            authorize_url = f'{cfg["auth_url"]}?{urlencode(params)}'
            return jsonify(
                {
                    "provider": provider,
                    "authorize_url": authorize_url,
                    "state": state,
                    "nonce": nonce,
                    "trace_id": trace_id,
                }
            )
        except Exception as e:
            tb = traceback.format_exc()
            current_app.logger.exception("Unhandled error in /oauth/start (trace_id=%s)", trace_id)
            return jsonify({"error": str(e), "trace_id": trace_id, "traceback": tb}), 500

    @auth_bp.route("/oauth/exchange", methods=["POST"])
    async def oauth_exchange():
        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        try:
            body = await request.get_json() or {}
            provider = (body.get("provider") or "").strip().lower()
            code = (body.get("code") or "").strip()
            redirect_uri = (body.get("redirect_uri") or "").strip()
            if provider not in {"google", "apple"}:
                return jsonify({"error": "unsupported provider", "trace_id": trace_id}), 400
            if not code:
                return jsonify({"error": "code is required", "trace_id": trace_id}), 400
            if not redirect_uri:
                return jsonify({"error": "redirect_uri is required", "trace_id": trace_id}), 400

            cfg = _oauth_cfg(provider)
            if not cfg["client_id"] or not cfg["client_secret"] or not cfg["token_url"]:
                return (
                    jsonify(
                        {
                            "error": f"{provider} oauth is not configured",
                            "trace_id": trace_id,
                            "missing": ["CLIENT_ID or CLIENT_SECRET or TOKEN_URL"],
                        }
                    ),
                    501,
                )

            token_form = {
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            if provider == "apple":
                token_form["grant_type"] = "authorization_code"

            async with aiohttp.ClientSession() as session:
                async with session.post(cfg["token_url"], data=token_form) as token_resp:
                    token_raw = await token_resp.json(content_type=None)
                    if token_resp.status >= 400:
                        return (
                            jsonify(
                                {
                                    "error": "token exchange failed",
                                    "provider": provider,
                                    "status": token_resp.status,
                                    "provider_response": token_raw,
                                    "trace_id": trace_id,
                                }
                            ),
                            502,
                        )

                userinfo = {}
                access_token = (token_raw or {}).get("access_token", "")
                if cfg["userinfo_url"] and access_token:
                    async with session.get(
                        cfg["userinfo_url"], headers={"Authorization": f"Bearer {access_token}"}
                    ) as user_resp:
                        if user_resp.status < 400:
                            userinfo = await user_resp.json(content_type=None)

            provider_sub, provider_email = _extract_oauth_identity(provider, token_raw or {}, userinfo)
            if not provider_sub:
                return (
                    jsonify(
                        {
                            "error": "failed to resolve oauth identity",
                            "provider": provider,
                            "trace_id": trace_id,
                        }
                    ),
                    502,
                )

            normalized_sub = provider_sub.replace("/", "_").replace(":", "_")
            user_id = f"{provider}_{normalized_sub}"[:128]
            password_placeholder = secrets.token_urlsafe(24)

            async with async_mysql_pool.session() as session:
                result = await session.execute(
                    select(AuthUser).where(AuthUser.user_id == user_id).limit(1)
                )
                user = result.scalars().one_or_none()
                if user is None:
                    user = AuthUser(
                        user_id=user_id,
                        password_hash=generate_password_hash(password_placeholder),
                        is_active=True,
                    )
                    session.add(user)
                    await session.commit()
                elif not user.is_active:
                    return jsonify({"error": "user is disabled", "trace_id": trace_id}), 403

            token = create_token(user_id)
            expires_in = int(current_app.config.get("JWT_EXPIRE_SECONDS", 7 * 24 * 3600))
            return (
                jsonify(
                    {
                        "user_id": user_id,
                        "token": token,
                        "token_type": "Bearer",
                        "expires_in": expires_in,
                        "provider": provider,
                        "provider_email": provider_email,
                        "trace_id": trace_id,
                    }
                ),
                200,
            )
        except Exception as e:
            tb = traceback.format_exc()
            current_app.logger.exception("Unhandled error in /oauth/exchange (trace_id=%s)", trace_id)
            return jsonify({"error": str(e), "trace_id": trace_id, "traceback": tb}), 500

    return auth_bp

