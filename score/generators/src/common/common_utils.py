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

"""Stateless utilities shared by ECU-model generators."""

import hashlib
import re


def generate_header_file_guard(path: str) -> str:
    """Build a readable guard with a 96-bit digest of the original relative path."""
    readable = re.sub(r"_+", "_", (path + "_").translate(str.maketrans(".-/\\", "____")).upper())
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:24].upper()
    guard = f"{readable}{digest}_"
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", guard) is None:
        raise ValueError(f"Header path cannot produce a non-reserved C++ include guard: {path!r}")
    return guard
