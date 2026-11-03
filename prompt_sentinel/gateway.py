"""OpenAI-compatible, text-only inspection gateway."""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .audit import AuditStore
from .config import Settings, load_settings
from .detector import DetectionUnavailable, Detector, Verdict


class InspectionInput(BaseModel):
    text: str
    role: str = "tool"


def _text_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(
        isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
        for part in content
    ):
        return "\n".join(part["text"] for part in content)
    raise HTTPException(422, "Only text content is supported in protected messages")


def create_app(
    settings: Settings | None = None,
    detector: Detector | None = None,
    audit: AuditStore | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    detector = detector or Detector(settings)
    audit = audit or AuditStore(settings.audit_db)
    app = FastAPI(title="Prompt-Sentinel", version="0.1.0")

    def inspect_and_record(text: str, role: str, source: str, request_id: str) -> Verdict:
        try:
            verdict = detector.inspect(text, role)
        except DetectionUnavailable as exc:
            audit.add(
                request_id,
                source,
                settings.provider,
                Verdict("error", role, ("detector_unavailable",), (), None, len(text)),
            )
            raise HTTPException(503, str(exc)) from exc
        audit.add(request_id, source, settings.provider, verdict)
        return verdict

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "provider": settings.provider,
            "semantic_enabled": settings.semantic_enabled,
            "semantic_loaded": not settings.semantic_enabled
            or getattr(detector.semantic_scorer, "_model", None) is not None,
        }

    @app.post("/inspect")
    def inspect(body: InspectionInput) -> dict:
        if body.role not in {"user", "tool"}:
            raise HTTPException(422, "role must be user or tool")
        request_id = str(uuid4())
        verdict = inspect_and_record(body.text, body.role, "demo", request_id)
        return {"request_id": request_id, **verdict.to_dict()}

    @app.get("/audit")
    def get_audit(
        limit: int = Query(100, ge=1, le=500),
        x_audit_token: str | None = Header(None),
    ) -> dict:
        if settings.audit_token and x_audit_token != settings.audit_token:
            raise HTTPException(401, "Audit token required")
        return {"counts": audit.counts(), "events": audit.recent(limit)}

    @app.post("/v1/chat/completions")
    async def chat(payload: dict) -> JSONResponse:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages or len(messages) > 100:
            raise HTTPException(422, "messages must be a nonempty list of at most 100 items")
        if payload.get("stream") is True:
            raise HTTPException(422, "Streaming is not supported in this MVP")
        request_id = str(uuid4())
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in {
                "system", "developer", "user", "assistant", "tool"
            }:
                raise HTTPException(422, "Invalid message role")
            role = message["role"]
            if role in settings.protected_roles:
                text = _text_content(message.get("content"))
                verdict = inspect_and_record(text, role, "gateway", request_id)
                if verdict.action == "block":
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Prompt-Sentinel blocked untrusted text",
                            "request_id": request_id,
                            "engines": verdict.engines,
                            "rule_ids": verdict.rule_ids,
                        },
                    )

        if settings.provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise HTTPException(503, "DEEPSEEK_API_KEY is not configured")
            url = "https://api.deepseek.com/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            url = f"{settings.ollama_base_url}/v1/chat/completions"
            headers = {}
        forwarded = dict(payload)
        forwarded["model"] = settings.upstream_model
        forwarded["stream"] = False
        try:
            async with httpx.AsyncClient(
                timeout=60, follow_redirects=False, transport=upstream_transport
            ) as client:
                response = await client.post(url, json=forwarded, headers=headers)
            if response.is_error:
                raise HTTPException(502, f"Upstream returned HTTP {response.status_code}")
            return JSONResponse(
                content=response.json(),
                headers={"X-Prompt-Sentinel-Request-ID": request_id},
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "Upstream is unavailable or returned invalid JSON") from exc

    return app
