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

from score.ecu_model.communication.binding import CommunicationBinding, NetworkKind, ProtocolKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, ServiceInterface
from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier
from score.parsers.franca_parser.model.fdepl.definition import (
    DeploymentElement,
    DeploymentParameter,
)
from score.parsers.franca_parser.model.fdepl.interface_deployment import (
    ArgumentDeployment,
    AttributeDeployment,
    BroadcastDeployment,
    EventGroup,
    InterfaceDeployment,
    MethodDeployment,
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
    _SERVICE_ID_PROPERTIES = {
        NetworkKind.SOMEIP: "SomeIpServiceID",
        NetworkKind.IPC: "IpcServiceId",
    }
    # TODO: Legacy maps every field deployment to these hosts regardless of its
    # resolved datatype. Preserve that behavior until datatype-aware selection is specified.
    _FIELD_HOSTS = {"arrays", "strings", "numbers", "integers", "floats", "booleans"}
    _HOSTS_BY_DEPLOYMENT_TYPE = {
        InterfaceDeployment: {"interfaces"},
        EventGroup: {"event_groups"},
        TypedefDeployment: {"typedefs", "strings"},
        ArrayDeployment: {"arrays", "strings"},
        StructDeployment: {"structs"},
        UnionDeployment: {"unions"},
        EnumerationDeployment: {"enumerations"},
        AttributeDeployment: {
            "attributes",
            "attribute_getters",
            "attribute_setters",
            "attribute_notifiers",
            *_FIELD_HOSTS,
        },
        BroadcastDeployment: {"broadcasts"},
        MethodDeployment: {"methods"},
    }

    def __init__(self) -> None:
        self._service_interface_map: dict[tuple[str, NetworkKind], ServiceInterface] = {}

    @property
    def service_Interface_map(self) -> dict[tuple[str, NetworkKind], ServiceInterface]:
        return self._service_interface_map

    # maintain somip/ipc for service interface mapping

    def apply_type_collection_deployment(self, deployment: TypeCollectionDeployment) -> None:
        """Apply a resolved FDEPL type-collection deployment to its FIDL target."""
        specification = deployment.specification
        if not isinstance(specification, DeploymentSpecification):
            raise ValueError("Unresolved deployment specification")
        for deployment_element in deployment.deployment_elements:
            self._apply_deployment_element(deployment_element, specification)

    def apply_interface_deployment(self, deployment: InterfaceDeployment) -> None:
        """Merge a resolved interface deployment into its binding-specific public model."""
        specification = deployment.specification
        if not isinstance(specification, DeploymentSpecification):
            raise ValueError("Unresolved deployment specification")
        target = deployment.target
        if not isinstance(target, InterfaceDefinition):
            raise ValueError("Unresolved interface deployment target")
        interface_key = target.fully_qualified_name
        network = self._network_for_specification(specification)
        if network is None:
            return
        service_id = self._service_id_for_deployment(deployment, specification, network)

        key = (interface_key, network)
        service_interface = self._service_interface_map.get(key)
        if service_interface is None:
            binding = CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=network)
            service_interface = ServiceInterface(
                name=target.name,
                namespace=target.namespace,
                design_element=target,
                deployment_binding=binding,
                service_id=service_id,
                broadcast_deployment_properties={name: {} for name in target.broadcasts},
                attribute_deployment_properties={name: {} for name in target.attributes},
                method_deployment_properties={name: {} for name in target.methods},
            )
            self._service_interface_map[key] = service_interface
        else:
            service_interface.service_id = service_id
        self._apply_deployment_element(deployment, specification, service_interface)

    def _service_id_for_deployment(
        self,
        deployment: InterfaceDeployment,
        specification: DeploymentSpecification,
        network: NetworkKind,
    ) -> int:
        property_name = self._SERVICE_ID_PROPERTIES[network]
        declaration = self._declarations_for_hosts(specification, {"interfaces"}).get(property_name)
        if declaration is None:
            raise ValueError(
                f"Deployment specification {specification.name.as_str} must declare "
                f"{property_name}: Integer for interfaces"
            )
        if (
            declaration.type_reference.property_type is not DeploymentPropertyType.INTEGER
            or declaration.type_reference.is_array
        ):
            raise ValueError(f"Deployment property {property_name} must be declared as Integer")

        parameter = next(
            (parameter for parameter in reversed(deployment.parameter_set) if parameter.name.as_str == property_name),
            None,
        )
        if parameter is None:
            raise ValueError(f"Interface deployment must directly set {property_name}")
        self._validate_value(parameter.value, declaration)
        return cast(int, self._normalize_value(parameter.value, declaration))

    @classmethod
    def _network_for_specification(cls, specification: DeploymentSpecification) -> NetworkKind | None:
        """Find the supported network named by a specification or any inherited specification."""
        networks: set[NetworkKind] = set()

        def collect(current: DeploymentSpecification) -> None:
            name = current.name.names[-1].as_str if current.name.names else ""
            if name == "someip":
                networks.add(NetworkKind.SOMEIP)
            elif name == "ipc":
                networks.add(NetworkKind.IPC)
            for base in current.base_specifications:
                if not isinstance(base, DeploymentSpecification):
                    raise ValueError("Unresolved base deployment specification")
                collect(base)

        collect(specification)
        if len(networks) > 1:
            raise ValueError(
                f"Deployment specification {specification.name.as_str} inherits both someip and ipc bindings"
            )
        return next(iter(networks), None)

    def _apply_event_group_reference(
        self,
        reference: object | None,
        specification: DeploymentSpecification,
        member_properties: dict[str, object],
    ) -> None:
        """Preserve legacy spec-scoped event-group data on the referencing member."""
        if reference is None or not reference.used_event_groups:
            return
        group_properties: dict[str, object] = {}
        for group in reference.used_event_groups:
            if group.name is None:
                raise ValueError("Event group reference requires a name")
            properties: dict[str, object] = {}
            self._apply_parameters(
                group, group.parameter_set, specification, self._HOSTS_BY_DEPLOYMENT_TYPE[EventGroup], properties
            )
            group_properties[group.name.as_str] = properties
        member_properties[f"event_groups#{specification.name.as_str}"] = group_properties

    def _apply_argument_deployments(
        self,
        arguments: dict[Identifier, ArgumentDeployment],
        specification: DeploymentSpecification,
        member_properties: dict[str, object],
        direction: str,
    ) -> None:
        if not arguments:
            return
        argument_properties = cast(
            dict[str, dict[str, object]], member_properties.setdefault(f"{direction}#arguments", {})
        )
        for name, argument in arguments.items():
            self._apply_parameters(
                argument.deployed_type,
                argument.parameter_set,
                specification,
                self._FIELD_HOSTS,
                argument_properties.setdefault(name.as_str, {}),
            )

    def _apply_deployment_element(
        self,
        deployment: DeploymentElement | InterfaceDeployment,
        specification: DeploymentSpecification,
        service_interface: ServiceInterface | None = None,
    ) -> None:
        hosts = self._HOSTS_BY_DEPLOYMENT_TYPE.get(type(deployment))
        if hosts is None:
            return
        if isinstance(deployment, InterfaceDeployment):
            if service_interface is None:
                raise ValueError("Interface deployment requires a service interface")
            self._apply_parameters(
                service_interface,
                deployment.parameter_set,
                specification,
                hosts,
                service_interface.interface_deployment_properties,
            )
            for element in deployment.deployment_elements:
                if isinstance(element, EventGroup):
                    self._apply_deployment_element(element, specification, service_interface)
            for element in deployment.deployment_elements:
                if not isinstance(element, EventGroup):
                    self._apply_deployment_element(element, specification, service_interface)
            return
        if isinstance(deployment, EventGroup):
            if service_interface is None:
                raise ValueError("Interface deployment requires a service interface")
            if deployment.name is None:
                raise ValueError("Event group deployment requires a name")
            if deployment.name in service_interface.event_groups:
                self._apply_parameters(deployment, deployment.parameter_set, specification, hosts, {})
            properties = service_interface.event_groups.setdefault(deployment.name, {})
            self._apply_parameters(
                deployment,
                deployment.parameter_set,
                specification,
                hosts,
                properties,
            )
            return
        if isinstance(deployment, AttributeDeployment):
            if service_interface is None:
                raise ValueError("Interface deployment requires a service interface")
            target = deployment.deployed_type
            if target is None:
                raise ValueError("Unresolved attribute deployment target")
            properties = service_interface.attribute_deployment_properties[target.name]
            self._apply_parameters(
                target,
                deployment.parameter_set,
                specification,
                hosts,
                properties,
            )
            self._apply_event_group_reference(deployment.event_groups, specification, properties)
            return
        target = deployment.deployed_type
        if isinstance(deployment, BroadcastDeployment):
            if target is None:
                raise ValueError("Unresolved broadcast deployment target")
            if service_interface is None:
                raise ValueError("Interface deployment requires a service interface")
            properties = service_interface.broadcast_deployment_properties[target.name]
            self._apply_parameters(target, deployment.parameter_set, specification, hosts, properties)
            self._apply_event_group_reference(deployment.event_groups, specification, properties)
            self._apply_argument_deployments(deployment.outputs, specification, properties, "outputs")
            return
        if isinstance(deployment, MethodDeployment):
            if target is None:
                raise ValueError("Unresolved method deployment target")
            if service_interface is None:
                raise ValueError("Interface deployment requires a service interface")
            properties = service_interface.method_deployment_properties[target.name]
            self._apply_parameters(target, deployment.parameter_set, specification, hosts, properties)
            self._apply_argument_deployments(deployment.inputs, specification, properties, "inputs")
            self._apply_argument_deployments(deployment.outputs, specification, properties, "outputs")
            return
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
            someip_width = target.deployment_properties.get("SomeIpEnumWidth", 1)
            if not isinstance(someip_width, int) or isinstance(someip_width, bool):
                raise ValueError(
                    f"Unsupported SomeIpEnumWidth value {someip_width!r}: "
                    f"expected int, got {type(someip_width).__name__}"
                )
            storage = cls._SOMEIP_ENUM_WIDTHS.get(someip_width, cls._ENUM_BACKING_TYPES["UInt64"])
        target.size, target.signed = storage

    def _apply_parameters(
        self,
        target: object,
        parameters: list[DeploymentParameter],
        specification: DeploymentSpecification,
        hosts: set[str],
        applied_properties: dict[str, object] | None = None,
    ) -> None:
        declarations = self._declarations_for_hosts(specification, hosts)
        if applied_properties is None:
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
