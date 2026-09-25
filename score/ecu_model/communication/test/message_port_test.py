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

from pydantic import ValidationError

from score.ecu_model.common.asil_level import AsilLevel
from score.ecu_model.communication.message_channel import MessageChannel
from score.ecu_model.communication.message_port import (
    ProvidedMessagePort,
    RequiredMessagePort,
)
from score.ecu_model.communication.protocol import ProtocolKind
from score.ecu_model.model import ModelRegistry


class TestMessagePort(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _channel(self) -> MessageChannel:
        return MessageChannel(
            name="SpeedChannel",
            data_type="SpeedData",
            channel_id=42,
        )

    def test_provided_message_port_preserves_payload_and_queue_metadata(self) -> None:
        channel = self._channel()
        port = ProvidedMessagePort(
            name="SpeedPort",
            channel=channel,
            debug_only=True,
            asil=AsilLevel.B,
            protocol=ProtocolKind.ARA_COM,
            max_published_messages=4,
        )

        self.assertEqual(port.name.as_str, "SpeedPort")
        self.assertIs(port.channel, channel)
        self.assertTrue(port.debug_only)
        self.assertEqual(port.asil, AsilLevel.B)
        self.assertEqual(port.max_published_messages, 4)

    def test_required_message_port_preserves_payload_and_queue_metadata(self) -> None:
        channel = self._channel()
        port = RequiredMessagePort(
            name="SpeedPort",
            channel=channel,
            debug_only=True,
            asil=AsilLevel.D,
            protocol=ProtocolKind.MW_DIAG,
            max_required_messages=8,
        )

        self.assertEqual(port.name.as_str, "SpeedPort")
        self.assertIs(port.channel, channel)
        self.assertTrue(port.debug_only)
        self.assertEqual(port.asil, AsilLevel.D)
        self.assertEqual(port.max_required_messages, 8)

    def test_required_message_port_defaults(self) -> None:
        channel = self._channel()
        port = RequiredMessagePort(name="SpeedPort", channel=channel, protocol=ProtocolKind.ARA_DIAG)

        self.assertFalse(port.debug_only)
        self.assertEqual(port.asil, AsilLevel.QM)
        self.assertEqual(port.max_required_messages, 1)
        self.assertIs(port.channel, channel)

    def test_queue_sizes_must_be_positive_integers(self) -> None:
        channel = self._channel()
        with self.assertRaises(ValidationError):
            ProvidedMessagePort(
                name="SpeedPort",
                channel=channel,
                protocol=ProtocolKind.ARA_COM,
                max_published_messages=0,
            )

        with self.assertRaises(ValidationError):
            ProvidedMessagePort(
                name="SpeedPort",
                channel=channel,
                protocol=ProtocolKind.ARA_COM,
                max_published_messages=-1,
            )

        with self.assertRaises(ValidationError):
            RequiredMessagePort(
                name="SpeedPort",
                channel=channel,
                protocol=ProtocolKind.MW_COM,
                max_required_messages=0,
            )

        with self.assertRaises(ValidationError):
            RequiredMessagePort(
                name="SpeedPort",
                channel=channel,
                protocol=ProtocolKind.MW_COM,
                max_required_messages=-1,
            )


if __name__ == "__main__":
    unittest.main()
