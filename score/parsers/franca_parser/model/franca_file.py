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

"""Shared parser models for Franca source files."""

from dataclasses import dataclass, field
from pathlib import Path

from score.ecu_model.common.common_name_types import QualifiedName


@dataclass(frozen=True)
class ImportedNamespace:
    """Resolved Franca import and its optional namespace filter."""

    file_path: Path
    namespace: QualifiedName | None
    is_wildcard: bool = False


@dataclass
class FrancaFileModel:
    """Common transformed result for a Franca source file."""

    file_path: Path
    namespace: QualifiedName | None
    imported_files: list[ImportedNamespace] = field(default_factory=list)


@dataclass(frozen=True)
class FrancaTransformationContext:
    """Source-file information available while a Franca file is transformed."""

    file_path: Path
    imported_files: list[ImportedNamespace]
