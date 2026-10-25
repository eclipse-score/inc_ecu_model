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

"""Render generator-owned templates without depending on generator models."""

from collections.abc import Mapping
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


class TemplateRenderer:
    """Load templates from one explicit directory and fail on missing variables."""

    def __init__(self, template_dir: Path) -> None:
        """Configure deterministic text rendering for the supplied templates."""
        self._environment = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
            newline_sequence="\n",
        )

    def render(self, template_name: str, context: Mapping[str, object]) -> str:
        """Return rendered text without creating output files."""
        return self._environment.get_template(template_name).render(context)
