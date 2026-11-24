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

"""Render the layouts used by one generation target as a single C++ header."""

from collections.abc import Sequence
from pathlib import Path

from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.common.template_renderer import TemplateRenderer
from score.generators.src.layout.element_layout import ElementLayout


class HeaderRenderer:
    """Render layout constants and their lookup table without writing files."""

    def __init__(self) -> None:
        """Load the layout-owned template from Bazel runfiles."""
        self._renderer = TemplateRenderer(Path(__file__).with_name("templates"))

    def render(self, path: str, layouts: Sequence[ElementLayout]) -> str:
        """Render the supplied, already deduplicated layouts."""
        return self._renderer.render(
            "layout.h.j2",
            {"guard": generate_header_file_guard(path), "layouts": layouts},
        )
