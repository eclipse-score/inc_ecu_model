# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

from __future__ import annotations

from functools import total_ordering

from pydantic import BaseModel, Field, field_validator, model_validator


@total_ordering
class Version(BaseModel):
    """Semantic version shared by ECU model objects."""

    major: int = Field(default=1, ge=0)
    minor: int = Field(default=0, ge=0)
    patch: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _validate_all_or_none_provided(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        specified_fields = {name for name in ("major", "minor", "patch") if name in data}
        if specified_fields and len(specified_fields) != 3:
            raise ValueError("Either specify none of major, minor and patch or specify all three")
        return data

    @field_validator("major", "minor", "patch", mode="before")
    @classmethod
    def _validate_decimal_integer(cls, value: object) -> int:
        if isinstance(value, bool):
            raise ValueError("Version numbers must be integers in decimal format")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdecimal():
            return int(value.strip())
        raise ValueError("Version numbers must be integers in decimal format")

    @model_validator(mode="after")
    def _validate_at_least_one_non_zero(self) -> "Version":
        if self.major == 0 and self.minor == 0 and self.patch == 0:
            raise ValueError("At least one of major, minor or patch must be greater than zero")
        return self

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
