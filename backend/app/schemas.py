from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    captcha_token: str
    consent: bool

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v) or not any(c.islower() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain upper, lower, and a digit, and be at least 12 characters.")
        return v

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must consent to the data processing policy to create an account.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    status: str
    input_type: str
    snp_overlap_count: int | None
    snp_overlap_total: int | None
    is_reliable: bool | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobDetailOut(JobOut):
    predictions: dict | None
    # Not a DB column -- computed per-request in the /jobs/{id} route, only
    # while status == queued. Not present on the /jobs list to avoid an N+1
    # count query there.
    queue_position: int | None = None
