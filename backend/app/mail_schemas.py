from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MailStateResponse(BaseModel):
    user_id: str
    mail: Dict[str, Any]
    enable_notifications: bool = False


class MailAttachment(MailRequest):
    id: str
    name: str
    size: str
    type: str
    url: str
    filename: str


class MailSendRequest(MailRequest):
    to: str
    cc: Optional[str] = ""
    bcc: Optional[str] = ""
    subject: Optional[str] = ""
    body: Optional[str] = ""
    attachments: List[MailAttachment] = Field(default_factory=list)
    draft_id: Optional[str] = None


class MailReplyRequest(MailRequest):
    thread_id: str
    body: str
    reply_all: bool = False
    reply_to_id: Optional[str] = None
    attachments: List[MailAttachment] = Field(default_factory=list)


class MailDraftRequest(MailRequest):
    draft_id: Optional[str] = None
    to: Optional[str] = ""
    cc: Optional[str] = ""
    bcc: Optional[str] = ""
    subject: Optional[str] = ""
    body: Optional[str] = ""
    attachments: List[MailAttachment] = Field(default_factory=list)


class MailDraftResponse(MailStateResponse):
    draft_id: Optional[str] = None


class MailEmailUpdates(MailRequest):
    read: Optional[bool] = None
    starred: Optional[bool] = None
    important: Optional[bool] = None
    folder: Optional[Literal["inbox", "sent", "drafts", "trash", "all-mail", "spam"]] = None
    labels: Optional[List[str]] = None
    category: Optional[Literal["primary", "social", "promotions", "updates"]] = None

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one email update is required")
        return self


class MailUpdateRequest(MailRequest):
    updates: MailEmailUpdates


class MailBulkUpdateRequest(MailRequest):
    email_ids: List[str] = Field(min_length=1)
    updates: MailEmailUpdates


class MailEmailIdsRequest(MailRequest):
    email_ids: List[str] = Field(min_length=1)


class MailLabelRequest(MailRequest):
    name: str
    color: Optional[str] = "#9ca3af"


class MailLabelToggleRequest(MailRequest):
    label_id: str
    action: Literal["add", "remove", "toggle"] = "toggle"


class MailLabelResponse(MailStateResponse):
    label: Optional[Dict[str, Any]] = None
