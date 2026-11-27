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

"""Resolve FDEPL references against transformed Franca file models."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.common import DataTypeBase, DataTypeKind
from score.ecu_model.data_types.identifier import QualifiedName
from score.parsers.franca_parser.model.fdepl.definition import DeploymentDefinition
from score.parsers.franca_parser.model.fdepl.fdepl_file import (
    FDEPLFileModel,
)
from score.parsers.franca_parser.model.fdepl.interface_deployment import (
    AttributeDeployment,
    BroadcastDeployment,
    EventGroup,
    InterfaceDeployment,
    MethodDeployment,
)
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentSpecification,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    ArrayDeployment,
    DatatypeDeployment,
    EnumerationDeployment,
    EnumValueDeployment,
    MapDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypedefDeployment,
    UnionDeployment,
)
from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
    ImportedNamespace,
)
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    matches_use_definition_reference,
    resolve_from_imported,
    resolve_from_local,
    select_single_match,
)


@dataclass
class PendingUseDefinition:
    """An unresolved use reference in one type-collection deployment."""

    reference: QualifiedName
    deployment: DeploymentDefinition
    index: int
    owning_file: FDEPLFileModel


class FDEPLResolver:
    """Resolve FDEPL specification and type-collection deployment references."""

    _EXPECTED_DATATYPE_KINDS = {
        TypedefDeployment: DataTypeKind.TYPEDEF,
        ArrayDeployment: DataTypeKind.ARRAY,
        EnumerationDeployment: DataTypeKind.ENUM,
        StructDeployment: DataTypeKind.STRUCT,
        UnionDeployment: DataTypeKind.UNION,
        MapDeployment: DataTypeKind.MAP,
    }

    def __init__(self, files: Mapping[Path, FrancaFileModel]) -> None:
        """Create a resolver over the transformed Franca file graph."""
        self._files = files

    def resolve_base_specification(
        self,
        reference: QualifiedName,
        owning_file: FDEPLFileModel,
    ) -> DeploymentSpecification:
        """Resolve a specification declared locally or in transformed FDEPL imports."""
        for local_specification in owning_file.specifications:
            if local_specification.name == reference:
                return local_specification
        for imported_file in self._files.values():
            if not isinstance(imported_file, FDEPLFileModel):
                continue
            namespace_length = 0 if imported_file.namespace is None else len(imported_file.namespace.names)
            local_specification_name = (
                reference if len(reference.names) == 1 else QualifiedName(reference.names[namespace_length:])
            )
            for imported_specification in imported_file.specifications:
                if imported_specification.name == local_specification_name:
                    return imported_specification
        raise ValueError(
            f"Could not resolve deployment base specification {reference.as_str} in {owning_file.file_path}"
        )

    def resolve_type_collection(
        self,
        reference: QualifiedName,
        imports: Iterable[ImportedNamespace],
        file_path: Path,
    ) -> TypeCollection:
        """Resolve one imported FIDL type collection or raise a contextual error."""
        matches: list[TypeCollection] = []
        for imported_namespace in imports:
            imported_file = self._files.get(imported_namespace.file_path)
            if not isinstance(imported_file, FIDLFileModel) or imported_file.namespace is None:
                continue
            namespace = imported_file.namespace.names
            if reference.names[: len(namespace)] != namespace:
                continue
            for type_collection in imported_file.type_collections:
                if (
                    type_collection.name is None and reference.names == namespace
                ) or type_collection.name == reference.names[-1]:
                    matches.append(type_collection)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"Could not resolve FIDL type collection {reference.as_str} in {file_path}")
        raise ValueError(f"Ambiguous FIDL type collection {reference.as_str} in {file_path}")

    def resolve_interface(
        self,
        reference: QualifiedName,
        imports: Iterable[ImportedNamespace],
        file_path: Path,
    ) -> InterfaceDefinition:
        """Resolve one interface target from the FIDL files imported by an FDEPL file."""
        return select_single_match(
            resolve_from_imported(
                reference,
                imports,
                self._files,
                FIDLFileModel,
                lambda imported_reference, imported_file, imported_namespace: resolve_from_local(
                    imported_reference,
                    imported_file.interfaces,
                    imported_file.namespace,
                    lambda interface: interface.name,
                    imported_namespace=imported_namespace,
                ),
            ),
            not_found_message=f"Could not resolve FIDL interface {reference.as_str} in {file_path}",
            ambiguous_message=f"Ambiguous FIDL interface {reference.as_str} in {file_path}",
            required=True,
        )

    @staticmethod
    def _resolve_interface_member(reference: object, members: object, kind: str, file_path: Path) -> object:
        """Resolve a named deployment member against one interface member collection."""
        reference_name = getattr(reference, "as_str", str(reference))
        candidates = members.values() if isinstance(members, dict) else members
        for member in candidates:
            if member.name.as_str == reference_name:
                return member
        raise ValueError(f"Could not resolve FIDL {kind} {reference_name} in {file_path}")

    def resolve_interface_deployment_elements(
        self,
        deployment: InterfaceDeployment,
        owning_file: FDEPLFileModel,
    ) -> None:
        """Bind interface deployment members, arguments, event groups, and local datatypes."""
        target = deployment.target
        if not isinstance(target, InterfaceDefinition):
            raise ValueError("Unresolved interface deployment target")
        event_groups = {
            element.name.as_str: element
            for element in deployment.deployment_elements
            if isinstance(element, EventGroup) and element.name is not None
        }

        for element in deployment.deployment_elements:
            if isinstance(element, EventGroup):
                if element.name is None:
                    raise ValueError("Event group deployment requires a name")
            elif isinstance(element, AttributeDeployment):
                element.deployed_type = self._resolve_interface_member(
                    element.deployed_type,
                    target.attributes,
                    "attribute",
                    owning_file.file_path,
                )
                self._resolve_event_group_references(element.event_groups, event_groups, owning_file.file_path)
            elif isinstance(element, MethodDeployment):
                element.deployed_type = self._resolve_interface_member(
                    element.deployed_type,
                    target.methods,
                    "method",
                    owning_file.file_path,
                )
                method = element.deployed_type
                element.inputs = self._resolve_argument_deployments(
                    element.inputs,
                    method.inputs,
                    owning_file.file_path,
                )
                element.outputs = self._resolve_argument_deployments(
                    element.outputs,
                    method.outputs,
                    owning_file.file_path,
                )
            elif isinstance(element, BroadcastDeployment):
                element.deployed_type = self._resolve_interface_member(
                    element.deployed_type,
                    target.broadcasts,
                    "broadcast",
                    owning_file.file_path,
                )
                element.outputs = self._resolve_argument_deployments(
                    element.outputs,
                    element.deployed_type.outputs,
                    owning_file.file_path,
                )
                self._resolve_event_group_references(element.event_groups, event_groups, owning_file.file_path)
            elif isinstance(element, DatatypeDeployment):
                self._resolve_interface_datatype(element, target, owning_file)

    def _resolve_interface_datatype(
        self,
        deployment: DatatypeDeployment,
        interface: InterfaceDefinition,
        owning_file: FDEPLFileModel,
    ) -> None:
        # Follow legacy lookup for bare names: imported anonymous collections before interface-local types.
        # Skip named collections because they require a collection-qualified reference.
        # Keep the last import per path and first match per file; reject cross-file ambiguity.
        def find_dt_from_anonymous_tc(
            reference: QualifiedName,
            imported_file: FIDLFileModel,
            imported_namespace: QualifiedName | None,
        ) -> list[DataTypeBase]:
            """Match a bare name in imported anonymous type collections."""
            return resolve_from_local(
                reference,
                (
                    datatype
                    for collection in imported_file.type_collections
                    if collection.name is None
                    for datatype in collection.datatypes
                ),
                imported_file.namespace,
                lambda datatype: datatype.name,
                imported_namespace=imported_namespace,
            )[:1]

        reference = QualifiedName((deployment.deployed_type,))
        imports_by_path = {
            imported.file_path: imported
            for imported in owning_file.imported_files
            if str(imported.file_path).endswith("fidl")
        }
        imported_datatype = select_single_match(
            resolve_from_imported(
                reference, imports_by_path.values(), self._files, FIDLFileModel, find_dt_from_anonymous_tc
            ),
            not_found_message=f"Could not resolve FIDL datatype {reference.as_str} in {owning_file.file_path}",
            ambiguous_message=f"Ambiguous FIDL datatype {reference.as_str} in {owning_file.file_path}",
        )
        datatypes = [imported_datatype] if imported_datatype is not None else interface.datatypes
        self._resolve_datatype(deployment, TypeCollection(name=None, datatypes=datatypes), owning_file)

    @classmethod
    def _resolve_argument_deployments(
        cls,
        deployments: dict[object, object],
        arguments: object,
        file_path: Path,
    ) -> dict[object, object]:
        """Resolve argument deployment names to the interface's DataTypeField models."""
        resolved: dict[object, object] = {}
        for deployment in deployments.values():
            deployment.deployed_type = cls._resolve_interface_member(
                deployment.deployed_type,
                arguments,
                "argument",
                file_path,
            )
            resolved[deployment.deployed_type.name] = deployment
        return resolved

    @staticmethod
    def _resolve_event_group_references(
        reference: object | None,
        event_groups: dict[str, EventGroup],
        file_path: Path,
    ) -> None:
        """Resolve event-group names within the containing interface deployment block."""
        if reference is None:
            return
        resolved_groups: list[EventGroup] = []
        for unresolved in reference.used_event_groups:
            name = unresolved.name.as_str if unresolved.name is not None else ""
            event_group = event_groups.get(name)
            if event_group is None:
                raise ValueError(f"Could not resolve event group {name} in {file_path}")
            resolved_groups.append(event_group)
        reference.used_event_groups = resolved_groups

    def resolve_datatype_deployments(
        self,
        deployment: TypeCollectionDeployment,
        owning_file: FDEPLFileModel,
    ) -> None:
        """Resolve datatype and child deployments to their FIDL declarations."""
        for deployment_element in deployment.deployment_elements:
            self._resolve_datatype(
                deployment_element,
                deployment.target,
                owning_file,
            )

    def _resolve_use_definition(
        self,
        reference: QualifiedName,
        owning_file: FDEPLFileModel,
    ) -> DeploymentDefinition | None:
        """Resolve a local or transformed-import type-collection or interface use reference."""
        local_groups = (owning_file.type_collection_deployments, owning_file.interface_deployments)
        for declarations in local_groups:
            matches = resolve_from_local(
                reference,
                (deployment for deployment in declarations if deployment.name is not None),
                owning_file.namespace,
                lambda deployment: deployment.name,
                matcher=matches_use_definition_reference,
            )
            resolved = select_single_match(
                matches,
                not_found_message=f"Could not resolve FDEPL use definition {reference.as_str} in {owning_file.file_path}",
                ambiguous_message=f"Ambiguous FDEPL use definition {reference.as_str} in {owning_file.file_path}",
            )
            if resolved is not None:
                return resolved
        for imported_namespace in owning_file.imported_files:
            imported_file = self._files.get(imported_namespace.file_path)
            if isinstance(imported_file, FDEPLFileModel):
                for declarations in (imported_file.type_collection_deployments, imported_file.interface_deployments):
                    matches = resolve_from_local(
                        reference,
                        (deployment for deployment in declarations if deployment.name is not None),
                        imported_file.namespace,
                        lambda deployment: deployment.name,
                        imported_namespace=imported_namespace.namespace,
                        matcher=matches_use_definition_reference,
                    )
                    resolved = select_single_match(
                        matches,
                        not_found_message=f"Could not resolve FDEPL use definition {reference.as_str} in {owning_file.file_path}",
                        ambiguous_message=f"Ambiguous FDEPL use definition {reference.as_str} in {owning_file.file_path}",
                    )
                    if resolved is not None:
                        return resolved
        return None

    def resolve_use_definitions(
        self,
        deployment: DeploymentDefinition,
        owning_file: FDEPLFileModel,
    ) -> list[PendingUseDefinition]:
        """Resolve visible use references and return only circular-import candidates."""
        pending_references: list[PendingUseDefinition] = []
        resolver = FDEPLResolver({**self._files, owning_file.file_path: owning_file})
        for index, reference in enumerate(deployment.use_definitions):
            if not isinstance(reference, QualifiedName):
                continue
            resolved = resolver._resolve_use_definition(reference, owning_file)
            if resolved is None:
                pending_references.append(PendingUseDefinition(reference, deployment, index, owning_file))
            else:
                deployment.use_definitions[index] = resolved
        return pending_references

    def resolve_pending_use_definitions(
        self,
        pending_references: list[PendingUseDefinition],
    ) -> None:
        """Resolve use references deferred behind circular FDEPL imports."""
        for pending in pending_references:
            resolved = self._resolve_use_definition(
                pending.reference,
                pending.owning_file,
            )
            if resolved is None:
                raise ValueError(
                    f"Could not resolve FDEPL use definition {pending.reference.as_str} "
                    f"in {pending.owning_file.file_path}"
                )
            pending.deployment.use_definitions[pending.index] = resolved

    @staticmethod
    def _resolve_datatype(
        deployment_element: DatatypeDeployment,
        type_collection: TypeCollection,
        owning_file: FDEPLFileModel,
    ) -> None:
        """Resolve one datatype deployment and any deployed members."""
        reference = deployment_element.deployed_type
        for datatype in type_collection.datatypes:
            if getattr(datatype, "name", None) is not None and datatype.name.as_str == reference.as_str:
                break
        else:
            raise ValueError(f"Could not resolve FIDL datatype {reference.as_str} in {owning_file.file_path}")
        expected_kind = FDEPLResolver._EXPECTED_DATATYPE_KINDS[type(deployment_element)]
        if datatype.kind != expected_kind:
            raise ValueError(
                f"FIDL datatype {reference.as_str} has kind {datatype.kind}, "
                f"expected {expected_kind} in {owning_file.file_path}"
            )
        deployment_element.deployed_type = datatype
        if isinstance(deployment_element, EnumerationDeployment):
            FDEPLResolver._resolve_deployment_targets(
                deployment_element.enumerators,
                getattr(datatype, "values", []),
                "enumeration value",
                owning_file,
            )
        if not isinstance(deployment_element, (StructDeployment, UnionDeployment)):
            return
        FDEPLResolver._resolve_deployment_targets(
            deployment_element.fields,
            getattr(datatype, "fields", []),
            "field",
            owning_file,
        )

    @staticmethod
    def _resolve_deployment_targets(
        deployments: list[EnumValueDeployment] | list[object],
        targets: list[object],
        target_kind: str,
        owning_file: FDEPLFileModel,
    ) -> None:
        targets_by_name = {
            target.name.as_str: target for target in targets if getattr(target, "name", None) is not None
        }
        for deployment in deployments:
            target_name = deployment.deployed_type.as_str
            target = targets_by_name.get(target_name)
            if target is None:
                raise ValueError(f"Could not resolve FIDL {target_kind} {target_name} in {owning_file.file_path}")
            deployment.deployed_type = target
