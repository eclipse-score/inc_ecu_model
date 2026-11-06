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

"""Transformed FIDL source file model."""

from dataclasses import dataclass, field

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.common import DataTypeBase
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import FrancaFileModel


@dataclass
class FIDLFileModel(FrancaFileModel):
    """File-level FIDL result containing its type collections."""

    type_collections: list[TypeCollection] = field(default_factory=list)
    interfaces: list[InterfaceDefinition] = field(default_factory=list)
    _datatype_in_tc_index: dict[str, DataTypeBase] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Index this file's declarations by their canonical FIDL identity."""
        for type_collection in self.type_collections:
            collection_parts = [name.as_str for name in self.namespace.names]
            if type_collection.name is not None:
                collection_parts.append(type_collection.name.as_str)
            for datatype in type_collection.datatypes:
                if not isinstance(datatype, DataTypeBase):
                    raise TypeError("FIDL type collections may only contain datatype definitions")
                identity = ".".join([*collection_parts, datatype.name.as_str])
                if identity in self._datatype_in_tc_index:
                    raise ValueError(f"Duplicate datatype identity '{identity}'")
                self._datatype_in_tc_index[identity] = datatype

    def lookup_datatype_in_tc(self, identity: str) -> DataTypeBase | None:
        """Return a declaration owned by this FIDL file, if present."""
        return self._datatype_in_tc_index.get(identity)
