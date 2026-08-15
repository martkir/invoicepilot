---
description: >-
  FastAPI application structure: project layout, app factory with lifespan,
  pydantic-settings configuration, Pydantic v2 schemas, dependency injection,
  router design, and the transactional service layer.
metadata:
  tags: [python, FastAPI, pydantic, SQLAlchemy, dependency-injection, structure]
---

# FastAPI Structure

## Project Layout

**Start here.** Flat, one file per concern, no directory holding a single module:

```text
my_app/
|-- app/
|   |-- main.py               # App factory, lifespan, middleware
|   |-- config.py             # Settings via pydantic-settings
|   |-- database.py           # SQLAlchemy engine + session
|   |-- dependencies.py       # Shared FastAPI dependencies
|   |-- models.py             # SQLAlchemy ORM models
|   |-- schemas.py            # Pydantic request/response schemas
|   |-- services.py           # Business logic
|   `-- routes.py             # All routers
|-- tests/
|   |-- conftest.py
|   `-- test_users.py
|-- pyproject.toml
`-- .env
```

This carries a real application a long way. Reading it means opening one file per concern, and adding an endpoint touches two.

**Grow only where it hurts.** When one of those files becomes genuinely hard to navigate, split *that* file — not all of them, and not preemptively. Splitting by entity keeps a change local to one folder:

```text
|   |-- users/                # Split when users outgrows the flat files
|   |   |-- schemas.py
|   |   |-- services.py
|   |   `-- routes.py
|   `-- invoices/
|       |-- schemas.py
|       |-- services.py
|       `-- routes.py
```

Splitting by *kind* instead — `routers/`, `models/`, `schemas/`, `services/`, each holding one file per entity — is the layout to avoid while the app is small. It scatters one conceptual change across four folders and makes the reader open four to understand one thing. It earns its place only when a single kind has many files and they genuinely share machinery.

Two rules that hold at any size:

- A directory containing one module should be a module
- The file names above are the split points; a chain of `app/api/v1/endpoints/users/handlers.py` is depth for its own sake

The examples below use the flat module names. Under the grown layout the imports change, nothing else does.

---

## App Factory and Lifespan

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables on startup for ease of use in dev/demo environments.
    # For strict production applications, manage schemas via Alembic migrations instead.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: close pooled resources.
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )

    app.include_router(routes.router, prefix="/users", tags=["users"])

    return app


app = create_app()
```

---

## Configuration with pydantic-settings

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "My App"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Pydantic-settings v2 safely evaluates mutable list literals directly
    allowed_origins: list[str] = ["http://localhost:3000"]
    allowed_methods: list[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["Authorization", "Content-Type"]
    allow_credentials: bool = True


settings = Settings()
```

---

## Pydantic Schemas (v2)

```python
# app/schemas.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    password_confirm: str

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]
```

Pydantic v2 uses `model_config`, not the v1 inner `class Config`. Treat any `class Config:` you find as a migration target.

---

## Dependency Injection

```python
# app/dependencies.py
from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
ActiveUserDep = Annotated[User, Depends(get_current_active_user)]
```

Authentication (`get_current_user`, `401`) stays separate from authorization (`get_current_active_user`, `403`) so the status codes carry accurate meaning.

---

## Router and Endpoint Design

```python
# app/routes.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import ActiveUserDep, DbDep
from app.schemas import UserCreate, UserResponse, UserUpdate, UserListResponse
from app.services import DuplicateUserError, UserService

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DbDep) -> UserResponse:
    service = UserService(db)
    try:
        return await service.create(payload)
    except DuplicateUserError:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: ActiveUserDep) -> UserResponse:
    return current_user


@router.get("/", response_model=UserListResponse)
async def list_users(
    db: DbDep,
    current_user: ActiveUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListResponse:
    service = UserService(db)
    users, total = await service.list(skip=skip, limit=limit)
    return UserListResponse(total=total, items=users)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DbDep,
    current_user: ActiveUserDep,
) -> UserResponse:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    service = UserService(db)
    try:
        user = await service.update(user_id, payload)
    except DuplicateUserError:
        raise HTTPException(status_code=400, detail="Email already registered")
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbDep,
) -> dict[str, str]:
    service = UserService(db)
    token = await service.authenticate(form_data.username, form_data.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": token, "token_type": "bearer"}
```

---

## Service Layer

```python
# app/services.py
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.schemas import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class DuplicateUserError(Exception):
    """Raised when a unique user field conflicts with an existing row."""


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, payload: UserCreate) -> User:
        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=pwd_context.hash(payload.password),
        )
        self.db.add(user)
        try:
            # Rely on atomic DB constraints rather than race-prone application-level prechecks
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise DuplicateUserError from exc
        await self.db.refresh(user)
        return user

    async def list(self, skip: int = 0, limit: int = 20) -> tuple[list[User], int]:
        total_result = await self.db.execute(select(func.count(User.id)))
        total = total_result.scalar_one()
        # Enforce explicit deterministic ordering to ensure reliable pagination
        result = await self.db.execute(
            select(User).order_by(User.id).offset(skip).limit(limit)
        )
        return list(result.scalars()), total

    async def update(self, user_id: int, payload: UserUpdate) -> User | None:
        user = await self.db.get(User, user_id)
        if user is None:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise DuplicateUserError from exc
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> str | None:
        user = await self.get_by_email(email)
        if user is None or not pwd_context.verify(password, user.hashed_password):
            return None
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        return jwt.encode(
            {"sub": str(user.id), "exp": expire},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
```

> **Note on database design:** Application-level unique handling requires an underlying unique database index (e.g. `unique=True` on your SQLAlchemy mapping attributes). Without the constraint, catching `IntegrityError` cannot prevent concurrent race conditions — nothing will raise.

Note the shape of this class: the route calls `UserService`, `UserService` calls the session. Two hops, no manager or repository in between. Add a third layer only when you can name what it decides.

When several services accumulate the same CRUD shape, extract a base class rather than copying methods — see [deduplication-patterns.md](deduplication-patterns.md). Keep it to one level of inheritance; if a subclass would exist only to set `model = X`, a parameterized function is flatter and reads better than a class hierarchy.
