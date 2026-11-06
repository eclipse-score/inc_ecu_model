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

import re
from collections.abc import Iterator

from pydantic import ConfigDict, Field, RootModel, field_validator

# Identifier syntax is the same across every supported IDL; only the namespace separator differs.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Identifier(RootModel[str]):
    """A single identifier, syntactically independent of the source IDL that declared it."""

    model_config = ConfigDict(frozen=True)

    root: str = Field(description="Identifier text, e.g. LaneInfo, speed_limit, uint32_t")

    @field_validator("root")
    @classmethod
    def _validate_root_is_an_identifier(cls, value: str) -> str:
        """Validate the identifier independently of any source IDL."""
        if not _IDENTIFIER_PATTERN.match(value):
            raise ValueError(
                f"Invalid identifier '{value}': must start with a letter or underscore, "
                "followed by letters, digits or underscores"
            )
        return value

    @property
    def as_str(self) -> str:
        return self.root

    def __str__(self) -> str:
        return self.as_str


class SelectableIdentifier(RootModel[str]):
    """An identifier with an optional colon-separated identifier suffix."""

    model_config = ConfigDict(frozen=True)

    root: str = Field(description="Identifier text with an optional suffix, e.g. query or query:first")

    @field_validator("root")
    @classmethod
    def _validate_root_is_selectable(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) > 2 or any(_IDENTIFIER_PATTERN.fullmatch(part) is None for part in parts):
            raise ValueError(f"Invalid selectable identifier '{value}': expected identifier or identifier:identifier")
        return value

    @property
    def as_str(self) -> str:
        return self.root

    def __str__(self) -> str:
        return self.as_str


class QualifiedName(RootModel[tuple[Identifier, ...]]):
    """An ordered sequence of identifier segments, syntactically independent of the source IDL that declared it."""

    model_config = ConfigDict(frozen=True)

    root: tuple[Identifier, ...] = Field(
        default=(),
        description="Ordered identifier segments, outer-to-inner",
    )

    @property
    def names(self) -> tuple[Identifier, ...]:
        return self.root

    def format(self, separator: str) -> str:
        """Render the qualified name using the provided separator."""
        return separator.join(name.as_str for name in self.root)

    @property
    def as_str(self) -> str:
        return self.format(".")

    def __str__(self) -> str:
        return self.as_str

    def __iter__(self) -> Iterator[Identifier]:  # type: ignore[override]
        return iter(self.root)
