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

"""Generate the member-owned SOME/IP layouts used by a loaded ECU model."""

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from score.ecu_model.model import ModelElement
from score.generators.src.common.output_writer import OutputWriter
from score.generators.src.layout.element_layout import ElementLayout
from score.generators.src.layout.header_renderer import HeaderRenderer
from score.generators.src.layout.layout_calculator import calculate_interface_layouts
from score.generators.src.layout.layout_collector import LayoutCollector
from score.generators.src.layout.layout_json_renderer import LayoutJsonRenderer


class LayoutGenerator:
    """Calculate member layouts and write C++ and JSON artifacts for the current model."""

    def __init__(
        self,
        header_path: str = "someip/layouts.h",
        report_path: str = "someip/member_layouts.json",
    ) -> None:
        """Choose artifact paths relative to the shared output root."""
        self._header_path = header_path
        self._report_path = report_path

    def generate(self, model: Mapping[str, Mapping[UUID, ModelElement]], output_dir: Path) -> None:
        """Generate layouts from concrete deployments without modifying the model."""
        layouts: dict[str, ElementLayout] = {}
        service_layouts = []
        for service in LayoutCollector.collect(model):
            member_layouts = calculate_interface_layouts(service)
            service_layouts.append((service, member_layouts))
            for layout in member_layouts.values():
                layouts[layout.layout_id] = layout
        if not layouts:
            return

        # Interning is process-local; only emit layouts reached in this call.
        selected = tuple(layouts[key] for key in sorted(layouts))
        content = HeaderRenderer().render(self._header_path, selected)
        writer = OutputWriter(output_dir)
        writer.write(self._header_path, content)
        writer.write(self._report_path, LayoutJsonRenderer().render(service_layouts))
