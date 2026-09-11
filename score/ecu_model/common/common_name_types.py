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

"""Generic identifier and qualified-name value objects."""

from pydantic import BaseModel, Field, RootModel


class Identifier(RootModel[str]):
    """One normalized identifier segment."""

    @property
    def as_str(self) -> str:
        """Return the identifier text."""
        return self.root

    def __str__(self) -> str:
        """Return the identifier text."""
        return self.as_str


class QualifiedName(BaseModel):
    """An ordered sequence of identifier segments."""

    names: list[Identifier] = Field(
        default_factory=list,
        description="Ordered identifier segments",
    )

    @property
    def as_str(self) -> str:
        """Return the dot-separated qualified name text."""
        return self.format(".")

    def __str__(self) -> str:
        """Return the dot-separated qualified name text."""
        return self.as_str

    def format(self, separator: str) -> str:
        """Render the qualified name using the provided separator."""
        return separator.join(name.as_str for name in self.names)
