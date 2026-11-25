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

"""Transformed FDEPL source file model."""

from dataclasses import dataclass, field

from score.parsers.franca_parser.model.fdepl.interface_deployment import InterfaceDeployment
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentSpecification,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    TypeCollectionDeployment,
)
from score.parsers.franca_parser.model.franca_file import FrancaFileModel


@dataclass
class FDEPLFileModel(FrancaFileModel):
    """File-level FDEPL result containing declared deployment specifications."""

    specifications: list[DeploymentSpecification] = field(default_factory=list)
    type_collection_deployments: list[TypeCollectionDeployment] = field(default_factory=list)
    interface_deployments: list[InterfaceDeployment] = field(default_factory=list)
