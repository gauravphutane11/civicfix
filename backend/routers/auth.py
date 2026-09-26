import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import (
    OTP_COOLDOWN_SECONDS,
    OTP_DEMO_MODE,
    OTP_EXPIRY_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_PROVIDER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_VERIFY_SERVICE_SID,
)
from ..database import get_db
from ..security import (
    create_access_token,
    get_current_user,
    hash_otp,
    hash_password,
    normalize_phone,
    verify_otp,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def now_utc():
    return datetime.now(timezone.utc)


def aware(value: Optional[datetime]):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _twilio_ready() -> bool:
    return bool(
        TWILIO_ACCOUNT_SID
        and TWILIO_AUTH_TOKEN
        and TWILIO_VERIFY_SERVICE_SID
    )


def _twilio_url(path: str) -> str:
    return (
        "https://verify.twilio.com/v2/Services/"
        f"{TWILIO_VERIFY_SERVICE_SID}/{path}"
    )


def _twilio_request(path: str, fields: dict[str, str]) -> dict:
    payload = urlencode(fields).encode("utf-8")
    request = Request(
        _twilio_url(path),
        data=payload,
        method="POST",
    )
    auth = base64.b64encode(
        f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")
    ).decode("ascii")
    request.add_header("Authorization", f"Basic {auth}")
    request.add_header(
        "Content-Type",
        "application/x-www-form-urlencoded",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = body.get("message") or "Twilio Verify request failed"
        except Exception:
            message = "Twilio Verify request failed"
        raise HTTPException(
            status_code=502,
            detail=message,
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to reach the OTP delivery service.",
        ) from exc


TWILIO_LOCALE_MAP = {
    "en": "en",
    "hi": "hi",
    "mr": "mr",
    "gu": "gu",
    "bn": "bn",
    "te": "te",
    "ta": "ta",
    "ml": "ml",
    "kn": "kn",
    "ur": "ur",
    "as": "as",
}


def _start_twilio(phone: str, language: Optional[str] = None):
    if not _twilio_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Real OTP delivery is not configured. Add "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and "
                "TWILIO_VERIFY_SERVICE_SID to the server environment."
            ),
        )

    fields = {
        "to": f"+91{phone}",
        "channel": "sms",
    }

    locale = TWILIO_LOCALE_MAP.get(
        (language or "").strip().lower()
    )

    if locale:
        fields["locale"] = locale

    try:
        return _twilio_request(
            "Verifications",
            fields,
        )
    except HTTPException:
        # Verify can reject an override when the selected template does not
        # provide that translation. Retry once using Twilio's country-code
        # language resolution / English fallback.
        if "locale" not in fields:
            raise
        fields.pop("locale", None)
        return _twilio_request(
            "Verifications",
            fields,
        )


def _check_twilio(phone: str, otp: str) -> bool:
    if not _twilio_ready():
        raise HTTPException(
            status_code=503,
            detail="Real OTP delivery is not configured on the server.",
        )
    result = _twilio_request(
        "VerificationCheck",
        {
            "to": f"+91{phone}",
            "code": otp.strip(),
        },
    )
    return result.get("status") == "approved"


@router.post("/register", response_model=schemas.AuthResponse, status_code=201)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    user = models.User(
        name=payload.name.strip(),
        email=email,
        phone=payload.phone.strip() if payload.phone else None,
        role=models.Role.CITIZEN.value,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return schemas.AuthResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
    )


@router.post("/login", response_model=schemas.AuthResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user and user.role == models.Role.CITIZEN.value:
        raise HTTPException(
            403,
            "Citizens use mobile OTP login. No password is required.",
        )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid email or password",
        )
    return schemas.AuthResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
    )


@router.post(
    "/citizen/request-otp",
    response_model=schemas.CitizenOtpRequestResponse,
)
def request_citizen_otp(
    payload: schemas.CitizenOtpRequest,
    db: Session = Depends(get_db),
):
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower() or None

    user = (
        db.query(models.User)
        .filter(
            models.User.phone == phone,
            models.User.role == models.Role.CITIZEN.value,
        )
        .first()
    )
    is_new = user is None

    if user is None:
        if len(name) < 2:
            raise HTTPException(
                400,
                "For first-time citizen access, enter your name.",
            )
        if email and db.query(models.User).filter(models.User.email == email).first():
            raise HTTPException(
                409,
                "That email is already linked to another account.",
            )
        user = models.User(
            name=name,
            email=email,
            phone=phone,
            role=models.Role.CITIZEN.value,
        )
        db.add(user)
        db.flush()
    elif email and not user.email:
        if (
            db.query(models.User)
            .filter(
                models.User.email == email,
                models.User.id != user.id,
            )
            .first()
        ):
            raise HTTPException(
                409,
                "That email is already linked to another account.",
            )
        user.email = email

    now = now_utc()
    previous = aware(user.otp_requested_at)
    if previous is not None:
        remaining = OTP_COOLDOWN_SECONDS - int(
            (now - previous).total_seconds()
        )
        if remaining > 0:
            raise HTTPException(
                429,
                f"Please wait {remaining} seconds before requesting another OTP.",
            )

    use_twilio = OTP_PROVIDER == "twilio" or (
        OTP_PROVIDER == "auto" and _twilio_ready()
    )

    demo_otp: Optional[str] = None

    try:
        if use_twilio:
            _start_twilio(phone, payload.language)
            user.otp_provider = "twilio"
            user.otp_hash = None
            message = "OTP sent to your mobile number."
            delivery_mode = "twilio"
        elif OTP_DEMO_MODE:
            otp = f"{secrets.randbelow(900000) + 100000:06d}"
            user.otp_provider = "demo"
            user.otp_hash = hash_otp(phone, otp)
            demo_otp = otp
            message = "Demo OTP generated for local/hackathon testing."
            delivery_mode = "demo"
        else:
            raise HTTPException(
                503,
                "OTP delivery is not configured. Enable Twilio Verify or demo mode.",
            )

        user.otp_expires_at = now + timedelta(
            minutes=OTP_EXPIRY_MINUTES
        )
        user.otp_attempts = 0
        user.otp_requested_at = now
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            502,
            "Unable to send the OTP right now.",
        ) from exc

    return schemas.CitizenOtpRequestResponse(
        message=message,
        expires_in_seconds=OTP_EXPIRY_MINUTES * 60,
        retry_after_seconds=OTP_COOLDOWN_SECONDS,
        demo_otp=demo_otp,
        is_new_user=is_new,
        delivery_mode=delivery_mode,
    )


@router.post("/citizen/verify-otp", response_model=schemas.AuthResponse)
def verify_citizen_otp(
    payload: schemas.CitizenOtpVerifyRequest,
    db: Session = Depends(get_db),
):
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    user = (
        db.query(models.User)
        .filter(
            models.User.phone == phone,
            models.User.role == models.Role.CITIZEN.value,
        )
        .first()
    )

    if not user or not user.otp_requested_at:
        raise HTTPException(400, "Request a new OTP first.")

    now = now_utc()
    expires = aware(user.otp_expires_at)

    if not expires or now >= expires:
        user.otp_hash = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        user.otp_requested_at = None
        user.otp_provider = None
        db.commit()
        raise HTTPException(
            400,
            "This OTP has expired. Request a new one.",
        )

    if user.otp_attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(
            429,
            "Too many incorrect OTP attempts. Request a new OTP.",
        )

    if user.otp_provider == "twilio":
        try:
            approved = _check_twilio(
                phone,
                payload.otp,
            )
        except HTTPException:
            raise
    else:
        approved = verify_otp(
            phone,
            payload.otp,
            user.otp_hash,
        )

    if not approved:
        user.otp_attempts += 1

        if user.otp_attempts >= OTP_MAX_ATTEMPTS:
            user.otp_hash = None
            user.otp_expires_at = None
            user.otp_requested_at = None
            user.otp_provider = None

        db.commit()

        remaining = max(
            0,
            OTP_MAX_ATTEMPTS - user.otp_attempts,
        )

        raise HTTPException(
            400,
            (
                "Incorrect OTP. No attempts remaining; request a new OTP."
                if remaining == 0
                else f"Incorrect OTP. {remaining} attempt(s) remaining."
            ),
        )

    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    user.otp_requested_at = None
    user.otp_provider = None
    db.commit()
    db.refresh(user)

    return schemas.AuthResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
    )


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
