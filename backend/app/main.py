import asyncio
import os
import platform
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mcp.server.fastmcp import FastMCP

from .config import Settings, get_settings
from .file_schemas import FileListResponse, FileUploadResponse, FileMetadata
from .file_store import (
    format_file_size,
    guess_mime_type,
    list_user_files,
    resolve_user_file,
    save_upload,
    split_file_id,
    split_stored_name,
)
from .mail import (
    apply_bulk_update,
    apply_delete,
    apply_empty_trash,
    apply_label_toggle,
    build_outgoing_email,
    build_reply_email,
    build_snippet,
    ensure_mail_state,
    find_email,
    generate_id,
    normalize_attachments,
    normalize_recipients,
)
from .mail_schemas import (
    MailBulkUpdateRequest,
    MailDraftRequest,
    MailDraftResponse,
    MailEmailIdsRequest,
    MailLabelRequest,
    MailLabelResponse,
    MailLabelToggleRequest,
    MailReplyRequest,
    MailSendRequest,
    MailStateResponse,
    MailUpdateRequest,
)
from .schemas import InfoResponse, StatePatchRequest, StateRequest, StateResponse
from .state_store import StateStore
from . import dynamic_events

settings = get_settings()
store = StateStore()
dynamic_events.set_store(store)

tags_metadata = [
    {"name": "state", "description": "Manage per-user experiment state"},
    {"name": "mail", "description": "Mail UI data and actions"},
    {"name": "files", "description": "User-scoped file uploads"},
    {"name": "system", "description": "Environment and health information"},
]


def build_file_url(filename: str) -> str:
    return f"{settings.api_prefix}/files/{filename}"


def build_file_metadata(
    *,
    file_id: str,
    filename: str,
    name: str,
    size_bytes: int,
    content_type: str,
) -> FileMetadata:
    return FileMetadata(
        id=file_id,
        name=name,
        size=format_file_size(size_bytes),
        type=content_type,
        url=build_file_url(filename),
        filename=filename,
    )


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"}


async def _fetch_remote_asset(url: str):
    def fetch():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MailHubWebProxy/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.headers, resp.read()

    return await asyncio.to_thread(fetch)


def _resolve_user_cookie(provided: Optional[str]) -> str:
    return provided if provided else str(uuid.uuid4())


# MCP server mirrors REST API operations via Streamable HTTP
mcp_server = FastMCP(
    name=f"{settings.app_name} MCP",
    instructions=(
        "Streamable HTTP MCP interface mirroring the REST API. "
        "Supply user_cookie to reuse the same per-user state; "
        "omit to generate a new cookie-backed state."
    ),
    host="0.0.0.0",
    streamable_http_path="/",
)

mcp_http_app = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MCP session manager so Streamable HTTP transport works when mounted
    mcp_ctx = mcp_server.session_manager.run()
    await mcp_ctx.__aenter__()
    try:
        yield
    finally:
        await mcp_ctx.__aexit__(None, None, None)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_tags=tags_metadata,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_id(
    request: Request, response: Response, settings: Settings = Depends(get_settings)
) -> str:
    cookie_override = request.query_params.get("cookie")
    user_id = cookie_override or request.cookies.get(settings.cookie_name)
    if not user_id:
        user_id = str(uuid.uuid4())
    response.set_cookie(
        settings.cookie_name,
        user_id,
        max_age=settings.cookie_max_age,
        httponly=False,
        samesite="lax",
    )
    return user_id


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # Minimal middleware that ensures each response carries a request id header.
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response: JSONResponse = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health", tags=["system"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/state-doc", tags=["system"])
async def state_doc():
    from pathlib import Path
    content = Path("/app/STATE.md").read_text(encoding="utf-8")
    return Response(content=content, media_type="text/plain; charset=utf-8")


@app.get(
    f"{settings.api_prefix}/proxy",
    tags=["system"],
    summary="Proxy remote assets",
)
async def proxy_asset(url: str) -> Response:
    if not _is_http_url(url):
        raise HTTPException(status_code=400, detail="Only http(s) URLs are allowed")
    try:
        status, headers, content = await _fetch_remote_asset(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Proxy request failed") from exc

    response = Response(content=content, status_code=status)
    content_type = headers.get("Content-Type")
    if content_type:
        response.headers["Content-Type"] = content_type
    cache_control = headers.get("Cache-Control")
    if cache_control:
        response.headers["Cache-Control"] = cache_control
    content_disposition = headers.get("Content-Disposition")
    if content_disposition:
        response.headers["Content-Disposition"] = content_disposition
    return response

# when build on the basesite, the below endpoints about state management should remain unchanged
@app.get(f"{settings.api_prefix}/state", response_model=StateResponse, tags=["state"])
async def get_state(user_id: str = Depends(get_user_id)) -> StateResponse:
    state = await store.get_state(user_id)
    return StateResponse(user_id=user_id, state=state)


@app.put(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Replace state",
)
async def put_state(payload: StateRequest, user_id: str = Depends(get_user_id)) -> StateResponse:
    time_data, action_data = dynamic_events.extract_dynamic_fields(payload.data)
    next_state = {"data": payload.data, "note": payload.note}
    if payload.meta is not None:
        next_state["meta"] = payload.meta
    state = await store.replace_state(user_id, next_state)
    if time_data or action_data:
        dynamic_events.start_dynamic_events(user_id, time_data, action_data)
    return StateResponse(user_id=user_id, state=state)


@app.patch(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Merge into existing state",
)
async def patch_state(
    payload: StatePatchRequest, user_id: str = Depends(get_user_id)
) -> StateResponse:
    state = await store.patch_state(user_id, patch=payload.data, note=payload.note)
    return StateResponse(user_id=user_id, state=state)


@app.delete(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Reset and clear state",
)
async def delete_state(user_id: str = Depends(get_user_id)) -> StateResponse:
    state = await store.reset_state(user_id)
    return StateResponse(user_id=user_id, state=state)


@app.get(
    f"{settings.api_prefix}/mail/state",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Fetch mail state",
)
async def get_mail_state(user_id: str = Depends(get_user_id)) -> MailStateResponse:
    def updater(existing_state):
        mail_state, changed = ensure_mail_state(existing_state.data, user_id)
        if changed:
            existing_state.data = mail_state
            existing_state.note = "Mail: initialized"
        return changed

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/send",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Send a new message",
)
async def send_mail(payload: MailSendRequest, user_id: str = Depends(get_user_id)) -> MailStateResponse:
    outgoing_ref: Dict[str, Any] = {}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        outgoing = build_outgoing_email(mail_state["user"], payload.model_dump())
        outgoing_ref.update(outgoing)
        mail_state["emails"].insert(0, outgoing)
        if payload.draft_id:
            mail_state["emails"] = [
                email for email in mail_state["emails"] if email.get("id") != payload.draft_id
            ]
        existing_state.data = mail_state
        existing_state.note = "Mail: sent message"
        return True

    state = await store.update_state(user_id, updater)
    await dynamic_events.check_action_triggers(user_id, outgoing_ref)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/reply",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Reply to an existing thread",
)
async def reply_mail(payload: MailReplyRequest, user_id: str = Depends(get_user_id)) -> MailStateResponse:
    reply_ref: Dict[str, Any] = {}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        thread_emails = [
            email for email in mail_state["emails"] if email.get("threadId") == payload.thread_id
        ]
        if not thread_emails:
            raise HTTPException(status_code=404, detail="Thread not found")

        source_email = None
        if payload.reply_to_id:
            source_email = find_email(thread_emails, payload.reply_to_id)
        if not source_email:
            def parse_ts(value: Optional[str]) -> datetime:
                try:
                    return datetime.fromisoformat(value or "")
                except ValueError:
                    return datetime.min.replace(tzinfo=timezone.utc)

            source_email = max(thread_emails, key=lambda email: parse_ts(email.get("timestamp")))

        reply_email = build_reply_email(
            mail_state["user"],
            source_email,
            payload.body,
            payload.reply_all,
            payload.attachments,
        )
        reply_ref.update(reply_email)
        mail_state["emails"].append(reply_email)
        existing_state.data = mail_state
        existing_state.note = "Mail: reply sent"
        return True

    state = await store.update_state(user_id, updater)
    await dynamic_events.check_action_triggers(user_id, reply_ref)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/draft",
    response_model=MailDraftResponse,
    tags=["mail"],
    summary="Create or update a draft",
)
async def save_draft(payload: MailDraftRequest, user_id: str = Depends(get_user_id)) -> MailDraftResponse:
    draft_ref: Dict[str, Optional[str]] = {"id": payload.draft_id}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        has_content = any(
            [
                payload.to,
                payload.cc,
                payload.bcc,
                payload.subject,
                payload.body,
                payload.attachments,
            ]
        )

        if payload.draft_id:
            existing = find_email(mail_state["emails"], payload.draft_id)
            if existing and existing.get("folder") == "drafts":
                existing["to"] = normalize_recipients(payload.to)
                existing["cc"] = normalize_recipients(payload.cc)
                existing["bcc"] = normalize_recipients(payload.bcc)
                existing["subject"] = payload.subject or "(no subject)"
                existing["body"] = payload.body or ""
                existing["snippet"] = build_snippet(existing["body"])
                existing["attachments"] = normalize_attachments(payload.attachments)
                existing["timestamp"] = datetime.now(timezone.utc).isoformat()
                existing_state.data = mail_state
                existing_state.note = "Mail: draft updated"
                draft_ref["id"] = existing["id"]
                return True

        if not has_content:
            return False

        draft_payload = payload.model_dump()
        draft_payload["folder"] = "drafts"
        new_draft = build_outgoing_email(mail_state["user"], draft_payload)
        new_draft["folder"] = "drafts"
        mail_state["emails"].insert(0, new_draft)
        existing_state.data = mail_state
        existing_state.note = "Mail: draft saved"
        draft_ref["id"] = new_draft["id"]
        return True

    state = await store.update_state(user_id, updater)
    return MailDraftResponse(user_id=user_id, mail=state.data, draft_id=draft_ref["id"])


@app.delete(
    f"{settings.api_prefix}/mail/draft/{{draft_id}}",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Delete a draft",
)
async def delete_draft(draft_id: str, user_id: str = Depends(get_user_id)) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        before = len(mail_state["emails"])
        mail_state["emails"] = [
            email for email in mail_state["emails"] if email.get("id") != draft_id
        ]
        if len(mail_state["emails"]) == before:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: draft deleted"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.patch(
    f"{settings.api_prefix}/mail/email/{{email_id}}",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Update a single email",
)
async def update_email(
    email_id: str, payload: MailUpdateRequest, user_id: str = Depends(get_user_id)
) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], [email_id], payload.updates)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: email updated"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/bulk",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Bulk update emails",
)
async def bulk_update_emails(
    payload: MailBulkUpdateRequest, user_id: str = Depends(get_user_id)
) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], payload.email_ids, payload.updates)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: bulk update"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/archive",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Archive emails",
)
async def archive_emails(
    payload: MailEmailIdsRequest, user_id: str = Depends(get_user_id)
) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], payload.email_ids, {"folder": "all-mail"})
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: archived"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/delete",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Delete emails or move to trash",
)
async def delete_emails(
    payload: MailEmailIdsRequest, user_id: str = Depends(get_user_id)
) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        mail_state["emails"], changed = apply_delete(mail_state["emails"], payload.email_ids)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: deleted"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/empty-trash",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Empty the trash folder",
)
async def empty_trash(user_id: str = Depends(get_user_id)) -> MailStateResponse:
    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        mail_state["emails"], changed = apply_empty_trash(mail_state["emails"])
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: trash emptied"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/mail/labels",
    response_model=MailLabelResponse,
    tags=["mail"],
    summary="Create a label",
)
async def create_label(
    payload: MailLabelRequest, user_id: str = Depends(get_user_id)
) -> MailLabelResponse:
    label_ref: Dict[str, Optional[Dict[str, Any]]] = {"label": None}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        new_label = {
            "id": generate_id(),
            "name": payload.name,
            "color": payload.color or "#9ca3af",
        }
        mail_state["labels"].append(new_label)
        existing_state.data = mail_state
        existing_state.note = "Mail: label created"
        label_ref["label"] = new_label
        return True

    state = await store.update_state(user_id, updater)
    return MailLabelResponse(user_id=user_id, mail=state.data, label=label_ref["label"])


@app.post(
    f"{settings.api_prefix}/mail/email/{{email_id}}/labels",
    response_model=MailStateResponse,
    tags=["mail"],
    summary="Toggle a label on an email",
)
async def toggle_label(
    email_id: str, payload: MailLabelToggleRequest, user_id: str = Depends(get_user_id)
) -> MailStateResponse:
    if payload.action not in {"add", "remove", "toggle"}:
        raise HTTPException(status_code=400, detail="Invalid label action")

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_label_toggle(
            mail_state["emails"], email_id, payload.label_id, payload.action
        )
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: labels updated"
        return True

    state = await store.update_state(user_id, updater)
    return MailStateResponse(user_id=user_id, mail=state.data)


@app.post(
    f"{settings.api_prefix}/files",
    response_model=FileUploadResponse,
    tags=["files"],
    summary="Upload files for the current user",
)
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_user_id),
) -> FileUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    uploaded: List[FileMetadata] = []
    for upload in files:
        saved = save_upload(user_id, upload)
        uploaded.append(
            build_file_metadata(
                file_id=saved["id"],
                filename=saved["filename"],
                name=saved["name"],
                size_bytes=saved["size_bytes"],
                content_type=saved["type"],
            )
        )
        await upload.close()

    return FileUploadResponse(user_id=user_id, files=uploaded)


@app.get(
    f"{settings.api_prefix}/files",
    response_model=FileListResponse,
    tags=["files"],
    summary="List files for the current user",
)
async def list_files(user_id: str = Depends(get_user_id)) -> FileListResponse:
    file_entries: List[FileMetadata] = []
    paths = sorted(list_user_files(user_id), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        filename = path.name
        file_entries.append(
            build_file_metadata(
                file_id=split_file_id(filename),
                filename=filename,
                name=split_stored_name(filename),
                size_bytes=path.stat().st_size,
                content_type=guess_mime_type(path),
            )
        )
    return FileListResponse(user_id=user_id, files=file_entries)


@app.get(
    f"{settings.api_prefix}/files/{{filename}}",
    response_class=FileResponse,
    tags=["files"],
    summary="Fetch a file by name for the current user",
)
async def get_file(filename: str, user_id: str = Depends(get_user_id)) -> FileResponse:
    path = resolve_user_file(user_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type=guess_mime_type(path),
        filename=split_stored_name(filename),
    )


@app.get(
    f"{settings.api_prefix}/info",
    response_model=InfoResponse,
    tags=["system"],
    summary="System and request info",
)
async def info(request: Request, user_id: str = Depends(get_user_id)) -> InfoResponse:
    runtime_env = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "env_mode": os.getenv("ENV", "dev"),
    }
    request_info: Dict[str, Any] = {
        "client": request.client.host if request.client else "unknown",
        "headers": dict(request.headers),
        "path": request.url.path,
        "method": request.method,
        "user_id": user_id,
    }
    return InfoResponse(
        app_name=settings.app_name,
        python_version=runtime_env["python_version"],
        env=runtime_env,
        request=request_info,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request.headers.get("x-request-id")},
    )

# these are for demo only, in later stages user should not have direct access to these functions
@mcp_server.tool(
    name="get_state",
    description="Fetch state for a user. Provide user_cookie to reuse identity; otherwise a new one is created.",
)
async def mcp_get_state(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    state = await store.get_state(user_id)
    return {"user_id": user_id, "state": state.model_dump()}


@mcp_server.tool(
    name="replace_state",
    description="Replace state for a user with provided data and optional note.",
)
async def mcp_replace_state(
    data: Dict[str, Any],
    note: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    time_data, action_data = dynamic_events.extract_dynamic_fields(data)
    state = await store.replace_state(user_id, {"data": data, "note": note})
    if time_data or action_data:
        dynamic_events.start_dynamic_events(user_id, time_data, action_data)
    return {"user_id": user_id, "state": state.model_dump()}


@mcp_server.tool(
    name="patch_state",
    description="Deep-merge data into existing state for a user; include user_cookie to target an existing session.",
)
async def mcp_patch_state(
    data: Dict[str, Any],
    note: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    state = await store.patch_state(user_id, patch=data, note=note)
    return {"user_id": user_id, "state": state.model_dump()}


@mcp_server.tool(
    name="reset_state",
    description="Reset the user's state to a new blank object.",
)
async def mcp_reset_state(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    state = await store.reset_state(user_id)
    return {"user_id": user_id, "state": state.model_dump()}


@mcp_server.tool(
    name="mail_get_state",
    description="Fetch mail state for a user. Provide user_cookie to reuse identity.",
)
async def mcp_mail_get_state(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, changed = ensure_mail_state(existing_state.data, user_id)
        if changed:
            existing_state.data = mail_state
            existing_state.note = "Mail: initialized"
        return changed

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_send",
    description="Send a new email. Provide to, cc, bcc, subject, body, attachments.",
)
async def mcp_mail_send(
    to: str,
    cc: Optional[str] = "",
    bcc: Optional[str] = "",
    subject: Optional[str] = "",
    body: Optional[str] = "",
    attachments: Optional[list] = None,
    draft_id: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    outgoing_ref: Dict[str, Any] = {}

    payload = {
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": subject,
        "body": body,
        "attachments": attachments or [],
        "draft_id": draft_id,
    }

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        outgoing = build_outgoing_email(mail_state["user"], payload)
        outgoing_ref.update(outgoing)
        mail_state["emails"].insert(0, outgoing)
        if draft_id:
            mail_state["emails"] = [
                email for email in mail_state["emails"] if email.get("id") != draft_id
            ]
        existing_state.data = mail_state
        existing_state.note = "Mail: sent message"
        return True

    state = await store.update_state(user_id, updater)
    await dynamic_events.check_action_triggers(user_id, outgoing_ref)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_reply",
    description="Reply to a thread. Provide thread_id and body; optional reply_all/reply_to_id.",
)
async def mcp_mail_reply(
    thread_id: str,
    body: str,
    reply_all: bool = False,
    reply_to_id: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    reply_ref: Dict[str, Any] = {}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        thread_emails = [
            email for email in mail_state["emails"] if email.get("threadId") == thread_id
        ]
        if not thread_emails:
            raise HTTPException(status_code=404, detail="Thread not found")

        source_email = None
        if reply_to_id:
            source_email = find_email(thread_emails, reply_to_id)
        if not source_email:
            def parse_ts(value: Optional[str]) -> datetime:
                try:
                    return datetime.fromisoformat(value or "")
                except ValueError:
                    return datetime.min.replace(tzinfo=timezone.utc)

            source_email = max(thread_emails, key=lambda email: parse_ts(email.get("timestamp")))

        reply_email = build_reply_email(mail_state["user"], source_email, body, reply_all)
        reply_ref.update(reply_email)
        mail_state["emails"].append(reply_email)
        existing_state.data = mail_state
        existing_state.note = "Mail: reply sent"
        return True

    state = await store.update_state(user_id, updater)
    await dynamic_events.check_action_triggers(user_id, reply_ref)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_save_draft",
    description="Create or update a draft. Provide to/cc/bcc/subject/body/attachments.",
)
async def mcp_mail_save_draft(
    to: Optional[str] = "",
    cc: Optional[str] = "",
    bcc: Optional[str] = "",
    subject: Optional[str] = "",
    body: Optional[str] = "",
    attachments: Optional[list] = None,
    draft_id: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    payload = {
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": subject,
        "body": body,
        "attachments": attachments or [],
    }
    draft_ref: Dict[str, Optional[str]] = {"id": draft_id}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        has_content = any([to, cc, bcc, subject, body, attachments])

        if draft_id:
            existing = find_email(mail_state["emails"], draft_id)
            if existing and existing.get("folder") == "drafts":
                existing["to"] = normalize_recipients(payload.get("to"))
                existing["cc"] = normalize_recipients(payload.get("cc"))
                existing["bcc"] = normalize_recipients(payload.get("bcc"))
                existing["subject"] = subject or "(no subject)"
                existing["body"] = body or ""
                existing["snippet"] = build_snippet(existing["body"])
                existing["attachments"] = normalize_attachments(payload.get("attachments"))
                existing["timestamp"] = datetime.now(timezone.utc).isoformat()
                existing_state.data = mail_state
                existing_state.note = "Mail: draft updated"
                draft_ref["id"] = existing["id"]
                return True

        if not has_content:
            return False

        draft_payload = {**payload, "folder": "drafts"}
        new_draft = build_outgoing_email(mail_state["user"], draft_payload)
        new_draft["folder"] = "drafts"
        mail_state["emails"].insert(0, new_draft)
        existing_state.data = mail_state
        existing_state.note = "Mail: draft saved"
        draft_ref["id"] = new_draft["id"]
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"], "draft_id": draft_ref["id"]}


@mcp_server.tool(
    name="mail_delete_draft",
    description="Delete a draft by id.",
)
async def mcp_mail_delete_draft(
    draft_id: str, user_cookie: Optional[str] = None
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        before = len(mail_state["emails"])
        mail_state["emails"] = [
            email for email in mail_state["emails"] if email.get("id") != draft_id
        ]
        if len(mail_state["emails"]) == before:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: draft deleted"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_update_email",
    description="Update a single email with the provided updates dict.",
)
async def mcp_mail_update_email(
    email_id: str,
    updates: Dict[str, Any],
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], [email_id], updates)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: email updated"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_bulk_update",
    description="Bulk update multiple emails with the same updates dict.",
)
async def mcp_mail_bulk_update(
    email_ids: list,
    updates: Dict[str, Any],
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], email_ids, updates)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: bulk update"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_archive",
    description="Archive emails by id (moves to all-mail).",
)
async def mcp_mail_archive(
    email_ids: list,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_bulk_update(mail_state["emails"], email_ids, {"folder": "all-mail"})
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: archived"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_delete",
    description="Delete emails or move to trash if not already there.",
)
async def mcp_mail_delete(
    email_ids: list,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        mail_state["emails"], changed = apply_delete(mail_state["emails"], email_ids)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: deleted"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_empty_trash",
    description="Delete all emails currently in the trash folder.",
)
async def mcp_mail_empty_trash(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        mail_state["emails"], changed = apply_empty_trash(mail_state["emails"])
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: trash emptied"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="mail_create_label",
    description="Create a new label with name and optional color.",
)
async def mcp_mail_create_label(
    name: str,
    color: Optional[str] = None,
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    label_ref: Dict[str, Optional[Dict[str, Any]]] = {"label": None}

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        new_label = {
            "id": generate_id(),
            "name": name,
            "color": color or "#9ca3af",
        }
        mail_state["labels"].append(new_label)
        existing_state.data = mail_state
        existing_state.note = "Mail: label created"
        label_ref["label"] = new_label
        return True

    state = await store.update_state(user_id, updater)
    return {
        "user_id": user_id,
        "mail": state.model_dump()["data"],
        "label": label_ref["label"],
    }


@mcp_server.tool(
    name="mail_toggle_label",
    description="Toggle a label on an email. action can be add/remove/toggle.",
)
async def mcp_mail_toggle_label(
    email_id: str,
    label_id: str,
    action: str = "toggle",
    user_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    if action not in {"add", "remove", "toggle"}:
        raise HTTPException(status_code=400, detail="Invalid label action")

    user_id = _resolve_user_cookie(user_cookie)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        changed = apply_label_toggle(mail_state["emails"], email_id, label_id, action)
        if not changed:
            return False
        existing_state.data = mail_state
        existing_state.note = "Mail: labels updated"
        return True

    state = await store.update_state(user_id, updater)
    return {"user_id": user_id, "mail": state.model_dump()["data"]}


@mcp_server.tool(
    name="info",
    description="Return backend environment info and the resolved user id.",
)
async def mcp_info(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    runtime_env = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "env_mode": os.getenv("ENV", "dev"),
    }
    return {
        "app_name": settings.app_name,
        "user_id": user_id,
        "env": runtime_env,
    }


# Mount MCP Streamable HTTP app at /mcp for remote access
app.mount("/mcp", mcp_http_app)
