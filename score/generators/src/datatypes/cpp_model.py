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

"""C++ declarations and header metadata consumed by renderers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CppAlias:
    """A named C++ type alias and its resolved C++ type expression."""

    name: str
    cpp_type: str


@dataclass(frozen=True)
class CppHeaderModel:
    """A completed declaration and its output-relative header metadata."""

    path: str
    guard: str
    namespaces: tuple[str, ...]
    includes: tuple[str, ...]
    declaration: CppAlias
