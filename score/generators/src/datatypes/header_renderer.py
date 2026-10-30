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

"""Adapt completed datatype headers to generator-owned templates."""

from pathlib import Path

from score.generators.src.common.template_renderer import TemplateRenderer
from score.generators.src.datatypes.cpp_model import CppHeaderModel


class HeaderRenderer:
    """Render supported datatype declarations to C++ headers."""

    def __init__(self) -> None:
        """Load templates shipped alongside this module in Bazel runfiles."""
        self._renderer = TemplateRenderer(Path(__file__).with_name("templates"))

    def render(self, header: CppHeaderModel) -> str:
        """Render one completed header without writing it to disk."""
        return self._renderer.render("datatype.h.j2", {"header": header})
