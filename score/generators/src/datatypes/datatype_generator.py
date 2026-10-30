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

"""Generate C++ datatype headers below the shared output root."""

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from score.ecu_model.model import ModelElement
from score.generators.src.common.output_writer import OutputWriter
from score.generators.src.datatypes.cpp_model import CppHeaderModel
from score.generators.src.datatypes.datatype_collector import DatatypeCollector
from score.generators.src.datatypes.datatype_utils import DatatypeUtils
from score.generators.src.datatypes.header_renderer import HeaderRenderer


class DatatypeGenerator:
    """Collect input types and immediately render and write each completed header."""

    def generate(self, model: Mapping[str, Mapping[UUID, ModelElement]], output_dir: Path) -> None:
        """Generate supported types from the merged model's datatype section."""
        selected = DatatypeCollector.collect(model)
        renderer = HeaderRenderer()
        writer = OutputWriter(output_dir)

        def on_header_ready(header: CppHeaderModel) -> None:
            writer.write(header.path, renderer.render(header))

        DatatypeUtils.build_type_registry(selected, on_header_ready)
