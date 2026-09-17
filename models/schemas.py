import re

from pydantic import BaseModel, Field, field_validator


class UserRegisterSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: str = Field(...)
    password: str = Field(..., min_length=8)

    @field_validator("username")
    def username_alphanumeric(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must contain only letters, numbers, and underscores")
        return v

    @field_validator("password")
    def password_complexity(cls, v):
        # Enforce: at least 8 chars, at least one uppercase, at least one digit, at least one special char from [@#$%^&*]
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")

        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include at least one uppercase letter.")

        if not re.search(r"\d", v):
            raise ValueError("Password must include at least one number.")

        if not re.search(r"[@#$%^&*]", v):
            raise ValueError("Password must include at least one special character from @#$%^&*.")
        return v

    @field_validator("email")
    def email_valid(cls, v):
        # simple, permissive regex for email validation to avoid external dependency
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address.")
        return v
