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

from score.ecu_model.communication.message_channel import MessageChannel
from score.ecu_model.model import ModelRegistry


class TestMessageChannel(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def test_message_channel_defaults(self) -> None:
        channel = MessageChannel(name="SpeedChannel", data_type="SpeedData")

        self.assertEqual(channel.name.as_str, "SpeedChannel")
        self.assertEqual(channel.data_type.as_str, "SpeedData")
        self.assertIsNone(channel.channel_id)
        self.assertIs(ModelRegistry.elements[channel.id], channel)

    def test_message_channel_with_channel_id(self) -> None:
        channel = MessageChannel(
            name="SpeedChannel",
            data_type="SpeedData",
            channel_id=42,
        )

        self.assertEqual(channel.channel_id, 42)

    def test_channel_id_must_be_non_negative_integer(self) -> None:
        with self.assertRaises(ValidationError):
            MessageChannel(
                name="SpeedChannel",
                data_type="SpeedData",
                channel_id=-1,
            )
        with self.assertRaises(ValidationError):
            MessageChannel(
                name="SpeedChannel",
                data_type="SpeedData",
                channel_id=True,  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
