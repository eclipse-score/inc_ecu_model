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

import unittest

from score.ecu_model.common.version import Version
from score.ecu_model.communication.detail.base_port import _BasePort
from score.ecu_model.communication.detail.message_port import _MessagePort
from score.ecu_model.communication.detail.service_port import _ServicePort
from score.ecu_model.communication.message_channel import MessageChannel
from score.ecu_model.communication.protocol import ProtocolKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, ServiceInterface
from score.ecu_model.model import ModelRegistry


class ConcretePort(_BasePort):
    """Concrete test port used to verify inherited _BasePort behavior."""


class TestBasePort(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def test_default_port_metadata(self) -> None:
        port = ConcretePort(name="VehicleState", protocol=ProtocolKind.MW_COM)

        self.assertEqual(port.name.as_str, "VehicleState")
        self.assertEqual(port.namespace.as_str, "adp")
        self.assertEqual(str(port.version), "1.0.0")
        self.assertIs(ModelRegistry.elements[port.id], port)

    def test_custom_namespace_and_version(self) -> None:
        port = ConcretePort(
            name="VehicleState",
            namespace="example.communication",
            version={"major": 2, "minor": 1, "patch": 0},
            protocol=ProtocolKind.ARA_COM,
        )

        self.assertEqual(port.namespace.as_str, "example.communication")
        self.assertEqual(str(port.version), "2.1.0")

    def test_base_port_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            _BasePort(name="VehicleState", protocol=ProtocolKind.MW_DIAG)

    def test_service_port_is_abstract(self) -> None:
        service_interface = ServiceInterface(
            name="VehicleStateDeployment",
            design_element=InterfaceDefinition(name="VehicleState", version=Version()),
        )
        with self.assertRaises(TypeError):
            _ServicePort(name="VehicleState", interface=service_interface, protocol=ProtocolKind.ARA_DIAG)

    def test_message_port_is_abstract(self) -> None:
        channel = MessageChannel(name="SpeedChannel", data_type="SpeedData")
        with self.assertRaises(TypeError):
            _MessagePort(name="SpeedPort", channel=channel, protocol=ProtocolKind.MW_COM)


if __name__ == "__main__":
    unittest.main()
