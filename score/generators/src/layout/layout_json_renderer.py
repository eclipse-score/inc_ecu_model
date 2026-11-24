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

"""Render calculated SOME/IP member layouts as a JSON report."""

import json
from collections.abc import Iterable, Mapping, Sequence
from uuid import UUID

from score.ecu_model.communication.service_interface import Attribute, Broadcast, Method, ServiceInterface
from score.generators.src.layout.element_layout import ElementLayout

type _Member = Attribute | Method | Broadcast


class LayoutJsonRenderer:
    """Render layouts grouped by interface and member kind."""

    def render(self, service_layouts: Sequence[tuple[ServiceInterface, Mapping[UUID, ElementLayout]]]) -> str:
        """Return a deterministic JSON report for the calculated service layouts."""
        service_interfaces: dict[str, dict[str, dict[str, object]]] = {}
        for service, layouts in service_layouts:
            design = service.design_element
            service_name = ".".join(name.as_str for name in (*service.namespace.names, service.name))
            interface = service_interfaces.setdefault(
                service_name,
                {"fields": {}, "methods": {}, "events": {}},
            )
            self._add_members(interface["fields"], design.fully_qualified_name, design.attributes.values(), layouts)
            self._add_members(interface["methods"], design.fully_qualified_name, design.methods.values(), layouts)
            self._add_members(interface["events"], design.fully_qualified_name, design.broadcasts.values(), layouts)

        report = {"service_interfaces": service_interfaces}
        return json.dumps(report, indent=2, sort_keys=True) + "\n"

    @staticmethod
    def _add_members(
        target: dict[str, object],
        interface_fqn: str,
        members: Iterable[_Member],
        layouts: Mapping[UUID, ElementLayout],
    ) -> None:
        for member in members:
            member_name = member.name.as_str
            member_fqn = f"{interface_fqn}.{member_name}"
            member_layouts = target.setdefault(member_name, {})
            layout_id = layouts[member.id].layout_id
            member_layouts[member_fqn] = layout_id
