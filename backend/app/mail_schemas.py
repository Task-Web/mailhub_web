from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MailStateResponse(BaseModel):
    user_id: str
    mail: Dict[str, Any]
    enable_notifications: bool = False


class MailSendRequest(BaseModel):
    to: str
    cc: Optional[str] = ""
    bcc: Optional[str] = ""
    subject: Optional[str] = ""
    body: Optional[str] = ""
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    draft_id: Optional[str] = None


class MailReplyRequest(BaseModel):
    thread_id: str
    body: str
    reply_all: bool = False
    reply_to_id: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class MailDraftRequest(BaseModel):
    draft_id: Optional[str] = None
    to: Optional[str] = ""
    cc: Optional[str] = ""
    bcc: Optional[str] = ""
    subject: Optional[str] = ""
    body: Optional[str] = ""
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class MailDraftResponse(MailStateResponse):
    draft_id: Optional[str] = None


class MailUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)


class MailBulkUpdateRequest(BaseModel):
    email_ids: List[str]
    updates: Dict[str, Any] = Field(default_factory=dict)


class MailEmailIdsRequest(BaseModel):
    email_ids: List[str]


class MailLabelRequest(BaseModel):
    name: str
    color: Optional[str] = "#9ca3af"


class MailLabelToggleRequest(BaseModel):
    label_id: str
    action: str = "toggle"


class MailLabelResponse(MailStateResponse):
    label: Optional[Dict[str, Any]] = None
