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

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from score.ecu_model.model import ModelElement, ModelRegistry

ParserResult = dict[UUID, ModelElement]


def load_and_merge(
    registry_pickle_files: Sequence[str],
) -> dict[str, object]:
    """Load and merge registry outputs already produced by parser Bazel targets."""
    merged_elements: ParserResult = {}

    for registry_path in registry_pickle_files:
        registry_file = Path(registry_path)
        if not registry_file.is_file():
            raise RuntimeError(f"Registry pickle file missing: {registry_file}")

        try:
            ModelRegistry.deserialize(registry_file.read_bytes())
            parser_elements = dict(ModelRegistry.elements)
        except Exception as error:
            raise RuntimeError(f"Failed to load registry pickle {registry_file}: {error}") from error

        duplicate_ids = merged_elements.keys() & parser_elements.keys()
        if duplicate_ids:
            duplicate_id = min(duplicate_ids, key=str)
            raise RuntimeError(f"Duplicate model element ID {duplicate_id} in {registry_file}")
        merged_elements.update(parser_elements)

    ModelRegistry.elements.clear()
    ModelRegistry.elements.update(merged_elements)
    return {"data_types": merged_elements}
