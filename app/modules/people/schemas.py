from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
#=====================================================

class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    description: str


class PhotoFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    photo_path: str | None = Field(default=None, max_length=500)

    @field_validator('photo_path')
    @classmethod
    def validate_photo(cls, value: str | None) -> str | None:
        # Reference a file managed by your upload endpoint, not a local system path.
        if value is not None:
            import re
            if not re.fullmatch(r'/media/people/[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)', value):
                raise ValueError('Expected /media/people/<file>.jpg|jpeg|png|webp')
        return value

class PersonCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)

class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_name: str
    last_name: str
    contact_email: str | None
    phone: str | None
    is_active: bool
    photo_path: str | None

class PersonPhotoWrite(PhotoFields):
    pass


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    login_email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=8, max_length=128)


class LoginRequest(AccountCreate):
    pass


class DevelopmentLoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    login_email: EmailStr = Field(max_length=320)


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    person_id: UUID
    login_email: str
    status: str
    roles: list[RoleRead]


class SchoolProfileCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    position: str = Field(default="", max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    short_bio: str = Field(default='', max_length=500)
    full_bio: str = Field(default='', max_length=10000)
    is_published: bool = False

class SchoolProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position: str
    person_id: UUID
    display_name: str
    short_bio: str
    full_bio: str
    photo_path: str | None
#=====================================================
