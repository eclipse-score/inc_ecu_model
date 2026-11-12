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

"""Apply resolved FDEPL datatype deployment properties to FIDL models."""

import logging
from typing import cast

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier
from score.parsers.franca_parser.model.fdepl.definition import (
    DeploymentElement,
    DeploymentParameter,
)
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentPropertyType,
    DeploymentSpecification,
    ParameterDeclaration,
    PropertyFlag,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    ArrayDeployment,
    EnumerationDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypedefDeployment,
    UnionDeployment,
)


class DeploymentPropertyApplier:
    """Apply legacy-compatible FDEPL properties to resolved FIDL datatype models."""

    _ENUM_BACKING_TYPES = {
        "UInt8": (8, False),
        "UInt16": (16, False),
        "UInt32": (32, False),
        "UInt64": (64, False),
        "Int8": (8, True),
        "Int16": (16, True),
        "Int32": (32, True),
        "Int64": (64, True),
    }
    _SOMEIP_ENUM_WIDTHS = {
        1: (8, False),
        2: (16, False),
        4: (32, False),
    }
    _DEFAULT_SOMEIP_ENUM_WIDTH = 1
    _FALLBACK_ENUM_BACKING_TYPE = "UInt64"
    _HOSTS_BY_DEPLOYMENT_TYPE = {
        TypedefDeployment: {"typedefs", "strings"},
        ArrayDeployment: {"arrays", "strings"},
        StructDeployment: {"structs"},
        UnionDeployment: {"unions"},
        EnumerationDeployment: {"enumerations"},
    }
    # TODO: Legacy maps every field deployment to these hosts regardless of its
    # resolved datatype. Preserve that behavior until datatype-aware selection is specified.
    _FIELD_HOSTS = {"arrays", "strings", "numbers", "integers", "floats", "booleans"}

    def apply_type_collection_deployment(self, deployment: TypeCollectionDeployment) -> None:
        """Apply a resolved FDEPL type-collection deployment to its FIDL target."""
        specification = deployment.specification
        if not isinstance(specification, DeploymentSpecification):
            raise ValueError("Unresolved deployment specification")
        for deployment_element in deployment.deployment_elements:
            self._apply_deployment_element(deployment_element, specification)

    def _apply_deployment_element(
        self,
        deployment: DeploymentElement,
        specification: DeploymentSpecification,
    ) -> None:
        hosts = self._HOSTS_BY_DEPLOYMENT_TYPE.get(type(deployment))
        if hosts is None:
            return
        target = deployment.deployed_type
        if not isinstance(target, DataTypeBase):
            raise ValueError("Unresolved datatype deployment target")
        self._apply_parameters(target, deployment.parameter_set, specification, hosts)
        if isinstance(deployment, (StructDeployment, UnionDeployment)):
            for field_deployment in deployment.fields:
                field_target = field_deployment.deployed_type
                if not isinstance(field_target, DataTypeField):
                    raise ValueError("Unresolved field deployment target")
                self._apply_parameters(
                    field_target,
                    field_deployment.parameter_set,
                    specification,
                    self._FIELD_HOSTS,
                )
        if isinstance(deployment, EnumerationDeployment):
            self._apply_enum_backing_type(cast(EnumDataType, target))
            # TODO: Legacy DeploymentRegistry does not register enumerator deployments.
            # Preserve that behavior until enum-value deployment storage is specified.
            return

    @classmethod
    def _apply_enum_backing_type(cls, target: EnumDataType) -> None:
        """Copy the deployed enum backing type into the normalized enum model fields."""
        backing_type = target.deployment_properties.get("EnumBackingType")
        if backing_type is not None:
            storage = cls._ENUM_BACKING_TYPES.get(backing_type) if isinstance(backing_type, str) else None
            if storage is None:
                raise ValueError(f"Unsupported EnumBackingType value {backing_type!r}")
        else:
            someip_width = target.deployment_properties.get("SomeIpEnumWidth", cls._DEFAULT_SOMEIP_ENUM_WIDTH)
            if not isinstance(someip_width, int) or isinstance(someip_width, bool):
                raise ValueError(
                    f"Unsupported SomeIpEnumWidth value {someip_width!r}: "
                    f"expected int, got {type(someip_width).__name__}"
                )
            storage = cls._SOMEIP_ENUM_WIDTHS.get(
                someip_width, cls._ENUM_BACKING_TYPES[cls._FALLBACK_ENUM_BACKING_TYPE]
            )
        target.size, target.signed = storage

    def _apply_parameters(
        self,
        target: DataTypeBase | DataTypeField,
        parameters: list[DeploymentParameter],
        specification: DeploymentSpecification,
        hosts: set[str],
    ) -> None:
        declarations = self._declarations_for_hosts(specification, hosts)
        applied_properties = target.deployment_properties
        for parameter in parameters:
            declaration = declarations.get(parameter.name.as_str)
            if declaration is None:
                logging.warning(
                    f"Ignoring undeclared deployment property {parameter.name.as_str} "
                    f"for {target.name.as_str} in specification {specification.name.as_str}"
                )
                continue
            self._validate_value(parameter.value, declaration)
            applied_properties[parameter.name.as_str] = self._normalize_value(
                parameter.value,
                declaration,
            )
        for declaration in declarations.values():
            if declaration.name.as_str in applied_properties:
                continue
            default_value = self._default_value(declaration)
            if default_value is not None:
                applied_properties[declaration.name.as_str] = self._normalize_value(
                    default_value,
                    declaration,
                )
            elif not self._is_optional(declaration):
                raise ValueError(f"Required deployment property {declaration.name.as_str} is not set")

    def _declarations_for_hosts(
        self,
        specification: DeploymentSpecification,
        hosts: set[str],
    ) -> dict[str, ParameterDeclaration]:
        declarations = {
            name: declaration for host in hosts for name, declaration in specification.hosts.get(host, {}).items()
        }
        for base_specification in specification.base_specifications:
            if not isinstance(base_specification, DeploymentSpecification):
                raise ValueError("Unresolved base deployment specification")
            for name, declaration in self._declarations_for_hosts(base_specification, hosts).items():
                declarations.setdefault(name, declaration)
        return declarations

    @staticmethod
    def _default_value(declaration: ParameterDeclaration) -> object | None:
        for liability in declaration.liabilities:
            if liability.property_flag is PropertyFlag.DEFAULT:
                return liability.default_value
        return None

    @staticmethod
    def _is_optional(declaration: ParameterDeclaration) -> bool:
        return any(liability.property_flag is PropertyFlag.OPTIONAL for liability in declaration.liabilities)

    def _validate_value(self, value: object, declaration: ParameterDeclaration) -> None:
        values = value if isinstance(value, list) else [value]
        if declaration.type_reference.is_array != isinstance(value, list):
            raise ValueError(f"Invalid shape for deployment property {declaration.name.as_str}")
        for item in values:
            if not self._is_valid_scalar(item, declaration):
                raise ValueError(f"Invalid value for deployment property {declaration.name.as_str}")

    @staticmethod
    def _is_valid_scalar(value: object, declaration: ParameterDeclaration) -> bool:
        property_type = declaration.type_reference.property_type
        if property_type is DeploymentPropertyType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if property_type is DeploymentPropertyType.STRING:
            return isinstance(value, str)
        if property_type is DeploymentPropertyType.BOOLEAN:
            return isinstance(value, bool)
        if property_type is DeploymentPropertyType.ENUM:
            return isinstance(value, Identifier) and value in declaration.type_reference.enumerators
        return True

    @staticmethod
    def _normalize_value(value: object, declaration: ParameterDeclaration) -> object:
        if isinstance(value, list):
            return [DeploymentPropertyApplier._normalize_value(item, declaration) for item in value]
        if declaration.type_reference.property_type is DeploymentPropertyType.ENUM and isinstance(value, Identifier):
            return value.as_str
        return value
