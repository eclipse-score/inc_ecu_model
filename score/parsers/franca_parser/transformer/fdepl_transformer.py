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

"""Lark transformer for FDEPL deployment specifications."""

from lark import v_args

from score.ecu_model.common.version import Version
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.parsers.franca_parser.deployment_property_applier import (
    DeploymentPropertyApplier,
)
from score.parsers.franca_parser.model.fdepl.definition import (
    DeploymentParameter,
)
from score.parsers.franca_parser.model.fdepl.fdepl_file import (
    FDEPLFileModel,
)
from score.parsers.franca_parser.model.fdepl.interface_deployment import (
    ArgumentDeployment,
    AttributeDeployment,
    BroadcastDeployment,
    EventGroup,
    EventGroupReference,
    InterfaceDeployment,
    MethodDeployment,
)
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentPropertyType,
    DeploymentPropertyTypeReference,
    DeploymentSpecification,
    ParameterDeclaration,
    ParameterLiability,
    PropertyFlag,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    ArrayDeployment,
    EnumerationDeployment,
    EnumValueDeployment,
    FieldDeployment,
    MapDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypedefDeployment,
    UnionDeployment,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
)
from score.parsers.franca_parser.model.parsed_file import ParsedFile
from score.parsers.franca_parser.transformer.base_transformer import (
    FrancaFileTransformer,
    franca_identifier,
    franca_integer,
)
from score.parsers.franca_parser.transformer.resolver.fdepl_resolver import (
    FDEPLResolver,
    PendingUseDefinition,
)


class FDEPLTransformer(FrancaFileTransformer):
    """Transform one FDEPL file into deployment specification models."""

    def __init__(
        self,
        transformed_files: dict[object, FrancaFileModel],
        parsed_file: ParsedFile,
        deployment_property_applier: DeploymentPropertyApplier,
    ) -> None:
        """Create a transformer for one parsed FDEPL source file."""
        super().__init__()
        self._transformed_files = transformed_files
        self._parsed_file = parsed_file
        self._resolver = FDEPLResolver(transformed_files)
        self._deployment_property_applier = deployment_property_applier
        self._pending_use_definitions: list[PendingUseDefinition] = []

    def transform_file(self) -> FDEPLFileModel:
        """Transform a parsed source file and retain its import context."""
        return self.transform(self._parsed_file.parse_tree)

    @staticmethod
    @v_args(inline=True)
    def start(model_root: FDEPLFileModel) -> FDEPLFileModel:
        """Unwrap the grammar's top-level start rule."""
        return model_root

    @v_args(inline=True)
    def fd_model(self, package: QualifiedName, *elements: object) -> FDEPLFileModel:
        """Collect specifications declared by an FDEPL file."""
        specifications: list[DeploymentSpecification] = []
        type_collection_deployments: list[TypeCollectionDeployment] = []
        interface_deployments: list[InterfaceDeployment] = []
        for element in elements:
            if isinstance(element, DeploymentSpecification):
                specifications.append(element)
            elif isinstance(element, TypeCollectionDeployment):
                type_collection_deployments.append(element)
            elif isinstance(element, InterfaceDeployment):
                interface_deployments.append(element)
        file_model = FDEPLFileModel(
            file_path=self._parsed_file.file_path,
            namespace=package,
            imported_files=self._parsed_file.imports,
            specifications=specifications,
            type_collection_deployments=type_collection_deployments,
            interface_deployments=interface_deployments,
        )
        for specification in file_model.specifications:
            specification.base_specifications = [
                self._resolver.resolve_base_specification(base_specification, file_model)
                for base_specification in specification.base_specifications
            ]
        for deployment in file_model.type_collection_deployments:
            deployment.specification = self._resolver.resolve_base_specification(
                deployment.specification,
                file_model,
            )
            self._resolver.resolve_datatype_deployments(deployment, file_model)
            self._pending_use_definitions.extend(self._resolver.resolve_use_definitions(deployment, file_model))
            self._deployment_property_applier.apply_type_collection_deployment(deployment)
        for deployment in file_model.interface_deployments:
            deployment.specification = self._resolver.resolve_base_specification(
                deployment.specification,
                file_model,
            )
            self._resolver.resolve_interface_deployment_elements(deployment, file_model)
            self._pending_use_definitions.extend(self._resolver.resolve_use_definitions(deployment, file_model))
            self._deployment_property_applier.apply_interface_deployment(deployment)
        return file_model

    @property
    def pending_use_definitions(self) -> list[PendingUseDefinition]:
        """Return use references unresolved after local and imported resolution."""
        return self._pending_use_definitions

    @staticmethod
    @v_args(inline=True)
    def fd_specification(name: QualifiedName, *elements: object) -> DeploymentSpecification:
        """Build a named specification with inherited specifications and hosts."""
        base_specifications = [element for element in elements if isinstance(element, QualifiedName)]
        hosts: dict[str, dict[str, ParameterDeclaration]] = {}
        for element in elements:
            if isinstance(element, tuple):
                host_name, parameters = element
                hosts[host_name] = parameters
        return DeploymentSpecification(name=name, base_specifications=base_specifications, hosts=hosts)

    @staticmethod
    @v_args(inline=True)
    def fd_host_decl(
        host_name: object, *parameters: ParameterDeclaration
    ) -> tuple[str, dict[str, ParameterDeclaration]]:
        """Group deployment property declarations by their target host."""
        host = str(host_name)
        for parameter in parameters:
            parameter.host = host
        return host, {parameter.name.as_str: parameter for parameter in parameters}

    @staticmethod
    @v_args(inline=True)
    def fd_parameter_decl(
        name: Identifier,
        type_reference: DeploymentPropertyTypeReference,
        *liabilities: ParameterLiability,
    ) -> ParameterDeclaration:
        """Create a deployment property declaration."""
        FDEPLTransformer._validate_liabilities(name, type_reference, liabilities)
        return ParameterDeclaration(
            host="",
            name=name,
            type_reference=type_reference,
            liabilities=list(liabilities),
        )

    @staticmethod
    def _validate_liabilities(
        name: Identifier,
        type_reference: DeploymentPropertyTypeReference,
        liabilities: tuple[ParameterLiability, ...],
    ) -> None:
        if len(liabilities) > 2:
            raise ValueError(f"Too many liability flags on parameter {name.as_str}")
        defaults = [liability for liability in liabilities if liability.property_flag is PropertyFlag.DEFAULT]
        if len(defaults) > 1:
            raise ValueError(f"More than one default parameter defined for {name.as_str}")
        if defaults and not FDEPLTransformer._is_value_compatible(
            defaults[0].default_value,
            type_reference,
        ):
            raise ValueError(f"Default parameter type mismatch for {name.as_str}")
        if defaults and type_reference.property_type is DeploymentPropertyType.ENUM:
            default_value = defaults[0].default_value
            values = default_value if isinstance(default_value, list) else [default_value]
            if any(value not in type_reference.enumerators for value in values):
                raise ValueError(f"Default parameter not defined for {name.as_str}")

    @staticmethod
    def _is_value_compatible(
        value: object,
        type_reference: DeploymentPropertyTypeReference,
    ) -> bool:
        values = value if isinstance(value, list) else [value]
        if not type_reference.is_array and isinstance(value, list):
            return False
        expected_types = {
            DeploymentPropertyType.INTEGER: int,
            DeploymentPropertyType.STRING: str,
            DeploymentPropertyType.BOOLEAN: bool,
            DeploymentPropertyType.ENUM: Identifier,
        }
        expected_type = expected_types.get(type_reference.property_type)
        return expected_type is None or all(isinstance(item, expected_type) for item in values)

    @staticmethod
    @v_args(inline=True)
    def fd_parameter_liability(value: object | None = None) -> ParameterLiability:
        """Transform optional and default property behavior."""
        if value is None:
            return ParameterLiability(property_flag=PropertyFlag.OPTIONAL)
        return ParameterLiability(property_flag=PropertyFlag.DEFAULT, default_value=value)

    @staticmethod
    @v_args(inline=True)
    def fd_type_ref(
        type_reference: DeploymentPropertyTypeReference, array_marker: object | None = None
    ) -> DeploymentPropertyTypeReference:
        """Apply the optional one-dimensional array designator."""
        type_reference.is_array = array_marker is not None
        return type_reference

    @staticmethod
    @v_args(inline=True)
    def fd_predefined_type(type_name: object) -> DeploymentPropertyTypeReference:
        """Transform a predefined FDEPL property type."""
        return DeploymentPropertyTypeReference(property_type=DeploymentPropertyType(str(type_name)))

    @staticmethod
    @v_args(inline=True)
    def fd_enum_type(*enumerators: Identifier) -> DeploymentPropertyTypeReference:
        """Transform an inline finite set of valid property values."""
        return DeploymentPropertyTypeReference(
            property_type=DeploymentPropertyType.ENUM,
            enumerators=list(enumerators),
        )

    @staticmethod
    @v_args(inline=True)
    def fd_extension_type(extension: Identifier) -> DeploymentPropertyTypeReference:
        """Transform a named property type extension."""
        return DeploymentPropertyTypeReference(
            property_type=DeploymentPropertyType.EXTENSION,
            extension=extension,
        )

    @staticmethod
    @v_args(inline=True)
    def integer(value: object) -> int:
        """Transform decimal, hexadecimal, and binary deployment values."""
        return franca_integer(value)

    @staticmethod
    @v_args(inline=True)
    def string(value: object) -> str:
        """Transform an FDEPL string literal."""
        return str(value).strip("'\"")

    @staticmethod
    @v_args(inline=True)
    def boolean(value: object) -> bool:
        """Transform an FDEPL Boolean literal."""
        return str(value) == "true"

    @staticmethod
    @v_args(inline=True)
    def fd_value(value: object) -> object:
        """Preserve a scalar property value."""
        return value

    @staticmethod
    @v_args(inline=True)
    def fd_value_array(*values: object) -> list[object]:
        """Transform a one-dimensional property value array."""
        return list(values)

    @staticmethod
    @v_args(inline=True)
    def fd_version_spec(major: object) -> Version:
        """Transform the optional major version of an interface deployment."""
        return Version(major=franca_integer(major), minor=0, patch=0)

    @staticmethod
    @v_args(inline=True)
    def fd_id_with_selector(
        name: Identifier,
        selector: Identifier | None = None,
    ) -> SelectableIdentifier:
        """Transform an overloaded method or broadcast name."""
        return SelectableIdentifier(f"{name}:{selector}" if selector is not None else str(name))

    @staticmethod
    @v_args(inline=True)
    def fd_parameter_set(*parameters: DeploymentParameter) -> tuple[str, list[DeploymentParameter]]:
        """Group the parameters applying to one interface deployment element."""
        return "parameter_set", list(parameters)

    @staticmethod
    @v_args(inline=True)
    def fd_interface_element(element: object) -> object:
        """Unwrap one interface deployment element."""
        return element

    @staticmethod
    @v_args(inline=True)
    def fd_argument(name: Identifier, *elements: object) -> ArgumentDeployment:
        """Build an unresolved argument deployment."""
        parameters = next(
            (element[1] for element in elements if isinstance(element, tuple) and element[0] == "parameter_set"),
            [],
        )
        return ArgumentDeployment(deployed_type=name, parameter_set=parameters)

    @staticmethod
    @v_args(inline=True)
    def fd_argument_list(*arguments: ArgumentDeployment) -> list[ArgumentDeployment]:
        """Collect argument deployments in declaration order."""
        return list(arguments)

    @staticmethod
    @v_args(inline=True)
    def fd_input_arguments(arguments: list[ArgumentDeployment]) -> tuple[str, list[ArgumentDeployment]]:
        """Label method input argument deployments."""
        return "inputs", arguments

    @staticmethod
    @v_args(inline=True)
    def fd_output_arguments(arguments: list[ArgumentDeployment]) -> tuple[str, list[ArgumentDeployment]]:
        """Label method or broadcast output argument deployments."""
        return "outputs", arguments

    @staticmethod
    @v_args(inline=True)
    def fd_method(name: SelectableIdentifier, *elements: object) -> MethodDeployment:
        """Build an unresolved method deployment and its argument deployments."""
        deployment = MethodDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
            elif isinstance(element, tuple) and element[0] == "inputs":
                deployment.inputs = {argument.deployed_type: argument for argument in element[1]}
            elif isinstance(element, tuple) and element[0] == "outputs":
                deployment.outputs = {argument.deployed_type: argument for argument in element[1]}
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_event_group(name: Identifier, *elements: object) -> EventGroup:
        """Build one named event-group deployment."""
        parameters = next(
            (element[1] for element in elements if isinstance(element, tuple) and element[0] == "parameter_set"),
            [],
        )
        return EventGroup(name=name, parameter_set=parameters)

    @staticmethod
    @v_args(inline=True)
    def fd_event_group_ref(*elements: object) -> EventGroupReference:
        """Build an event-group reference with unresolved group names."""
        reference = EventGroupReference()
        for element in elements:
            if isinstance(element, Identifier):
                reference.used_event_groups.append(EventGroup(name=element))
            elif isinstance(element, tuple) and element[0] == "parameter_set":
                reference.parameter_set = element[1]
        return reference

    @staticmethod
    @v_args(inline=True)
    def fd_attribute(name: Identifier, *elements: object) -> AttributeDeployment:
        """Build an unresolved attribute deployment."""
        deployment = AttributeDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, EventGroupReference):
                deployment.event_groups = element
            elif isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_broadcast(name: SelectableIdentifier, *elements: object) -> BroadcastDeployment:
        """Build an unresolved broadcast deployment."""
        deployment = BroadcastDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, EventGroupReference):
                deployment.event_groups = element
            elif isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
            elif isinstance(element, tuple) and element[0] == "outputs":
                deployment.outputs = {argument.deployed_type: argument for argument in element[1]}
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_general(*elements: object) -> TypeCollectionDeployment | InterfaceDeployment:
        """Attach the shared deployment specification to its root element."""
        specification = next((element for element in elements if isinstance(element, QualifiedName)), None)
        deployment = next(
            (element for element in elements if isinstance(element, (TypeCollectionDeployment, InterfaceDeployment))),
            None,
        )
        if specification is None or deployment is None:
            raise TypeError("fd_general requires a specification and deployment definition")
        deployment.specification = specification
        return deployment

    @v_args(inline=True)
    def fd_interface(
        self,
        target: QualifiedName,
        *elements: object,
    ) -> InterfaceDeployment:
        """Resolve the imported interface before constructing its deployment."""
        deployment = InterfaceDeployment(
            target=self._resolver.resolve_interface(target, self._parsed_file.imports, self._parsed_file.file_path)
        )
        for element in elements:
            if isinstance(element, Version):
                deployment.version = element
            elif isinstance(element, QualifiedName):
                deployment.name = element
            elif isinstance(element, tuple) and element[0] == "use":
                deployment.use_definitions.append(element[1])
            elif isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
            elif isinstance(
                element,
                (
                    ArrayDeployment,
                    AttributeDeployment,
                    BroadcastDeployment,
                    EnumerationDeployment,
                    EventGroup,
                    MethodDeployment,
                    MapDeployment,
                    StructDeployment,
                    TypedefDeployment,
                    UnionDeployment,
                ),
            ):
                deployment.deployment_elements.append(element)
        return deployment

    @v_args(inline=True)
    def fd_types(
        self,
        target: QualifiedName,
        *elements: object,
    ) -> TypeCollectionDeployment:
        """Resolve the imported type collection before constructing its deployment."""
        deployment = TypeCollectionDeployment(
            target=self._resolver.resolve_type_collection(
                target, self._parsed_file.imports, self._parsed_file.file_path
            )
        )
        for element in elements:
            if isinstance(element, QualifiedName):
                deployment.name = element
            elif isinstance(element, tuple) and element[0] == "use":
                deployment.use_definitions.append(element[1])
            elif isinstance(element, int):
                deployment.version_major = element
            elif isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
            elif isinstance(
                element,
                (
                    StructDeployment,
                    UnionDeployment,
                    TypedefDeployment,
                    ArrayDeployment,
                    EnumerationDeployment,
                    MapDeployment,
                ),
            ):
                deployment.deployment_elements.append(element)
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_type_definition(deployment: object) -> object:
        """Unwrap one datatype deployment definition."""
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_use_definition(reference: QualifiedName) -> tuple[str, QualifiedName]:
        """Mark one unresolved type-collection deployment use reference."""
        return "use", reference

    @staticmethod
    @v_args(inline=True)
    def fd_struct(name: Identifier, *elements: object) -> StructDeployment:
        """Create an unresolved struct deployment and its field deployments."""
        deployment = StructDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, DeploymentParameter):
                deployment.parameter_set.append(element)
            elif isinstance(element, FieldDeployment):
                deployment.fields.append(element)
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_union(name: Identifier, *elements: object) -> UnionDeployment:
        """Create an unresolved union deployment and its field deployments."""
        deployment = UnionDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, DeploymentParameter):
                deployment.parameter_set.append(element)
            elif isinstance(element, FieldDeployment):
                deployment.fields.append(element)
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_type_def(
        name: Identifier,
        *elements: object,
    ) -> TypedefDeployment:
        """Create an unresolved typedef deployment."""
        return TypedefDeployment(
            deployed_type=name,
            parameter_set=FDEPLTransformer._parameter_set_from(elements),
        )

    @staticmethod
    @v_args(inline=True)
    def fd_field(name: Identifier, *elements: object) -> FieldDeployment:
        """Create an unresolved struct field deployment."""
        parameters = FDEPLTransformer._parameter_set_from(elements)
        return FieldDeployment(deployed_type=name, parameter_set=parameters)

    @staticmethod
    @v_args(inline=True)
    def fd_array(name: Identifier, *elements: object) -> ArrayDeployment:
        """Create an unresolved array deployment."""
        parameters = FDEPLTransformer._parameter_set_from(elements)
        return ArrayDeployment(deployed_type=name, parameter_set=parameters)

    @staticmethod
    @v_args(inline=True)
    def fd_enumeration(
        name: Identifier,
        *elements: object,
    ) -> EnumerationDeployment:
        """Create an unresolved enumeration deployment."""
        deployment = EnumerationDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, DeploymentParameter):
                deployment.parameter_set.append(element)
            elif isinstance(element, EnumValueDeployment):
                deployment.enumerators.append(element)
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_parameter_value(parameter: DeploymentParameter) -> DeploymentParameter:
        """Unwrap an enum-level deployment-property assignment."""
        return parameter

    @staticmethod
    @v_args(inline=True)
    def fd_enum_value(
        name: Identifier,
        *elements: object,
    ) -> EnumValueDeployment:
        """Create an unresolved deployment for one enumeration value."""
        return EnumValueDeployment(
            deployed_type=name,
            parameter_set=FDEPLTransformer._parameter_set_from(elements),
        )

    @staticmethod
    @v_args(inline=True)
    def fd_map(name: Identifier, *elements: object) -> MapDeployment:
        """Create an unresolved map deployment with key and value properties."""
        deployment = MapDeployment(deployed_type=name)
        for element in elements:
            if isinstance(element, tuple) and element[0] == "parameter_set":
                deployment.parameter_set = element[1]
            elif isinstance(element, tuple):
                position, parameters = element
                if position == "key":
                    deployment.key = parameters
                elif position == "value":
                    deployment.value = parameters
        return deployment

    @staticmethod
    @v_args(inline=True)
    def fd_map_key(*elements: object) -> tuple[str, list[DeploymentParameter]]:
        """Group raw deployment properties for a map key."""
        return "key", FDEPLTransformer._parameter_set_from(elements)

    @staticmethod
    @v_args(inline=True)
    def fd_map_value(*elements: object) -> tuple[str, list[DeploymentParameter]]:
        """Group raw deployment properties for a map value."""
        return "value", FDEPLTransformer._parameter_set_from(elements)

    @staticmethod
    def _parameter_set_from(elements: tuple[object, ...]) -> list[DeploymentParameter]:
        """Extract a parameter list produced by the shared FDEPL parameter-set rule."""
        return next(
            (element[1] for element in elements if isinstance(element, tuple) and element[0] == "parameter_set"),
            [],
        )

    @staticmethod
    def fd_type_overwrites(_: object) -> None:
        """Accept unsupported type-overwrite syntax without modeling it yet."""
        return None

    @staticmethod
    @v_args(inline=True)
    def fd_parameter(name: Identifier, value: object) -> DeploymentParameter:
        """Preserve one raw deployment-property assignment."""
        return DeploymentParameter(name=name, value=value)

    @staticmethod
    @v_args(inline=True)
    def fd_valid_id(name: object) -> Identifier:
        """Build an identifier using the FDEPL keyword set."""
        return franca_identifier(name)

    @staticmethod
    def fd_fqn(names: list[Identifier]) -> QualifiedName:
        """Build an FDEPL fully qualified name."""
        return QualifiedName(tuple(names))

    @staticmethod
    @v_args(inline=True)
    def fd_keywords(keyword: object) -> Identifier:
        """Build an escaped FDEPL keyword identifier."""
        return franca_identifier(keyword)
