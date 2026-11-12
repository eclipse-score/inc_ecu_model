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

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from score.ecu_model.architecture.activity import Activity
from score.ecu_model.architecture.application import Application
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import RegisteredModelElement


class ChainNode(RegisteredModelElement):
    """One activity in a chain together with the activities that trigger it."""

    activity: Activity = Field(description="Activity scheduled by this node")
    triggered_by: list[Activity] = Field(
        default_factory=list,
        description="Predecessor activities whose completion triggers this node",
    )


class Chain(RegisteredModelElement):
    """Process-overarching schedule, modelled as a directed acyclic graph of activity trigger dependencies."""

    name: Identifier = Field(description="Identifier of the chain, unique within the owning ECU")
    namespace: QualifiedName = Field(
        default_factory=QualifiedName,
        description="Namespace in which the chain is declared",
    )
    cycle_time: timedelta = Field(description="Cycle time at which the whole chain is triggered")
    applications: list[Application] = Field(
        min_length=1,
        description="Applications participating in this chain",
    )
    nodes: list[ChainNode] = Field(
        min_length=1,
        description="Activity nodes forming the trigger dependency graph",
    )

    @field_validator("cycle_time")
    @classmethod
    def _validate_positive_cycle_time(cls, value: timedelta) -> timedelta:
        if value <= timedelta(0):
            raise ValueError("cycle_time must be positive")
        return value

    @model_validator(mode="after")
    def _validate_chain_graph(self) -> Chain:
        node_by_activity = self._validate_unique_activities()
        self._validate_application_membership()
        self._validate_trigger_references(node_by_activity)
        self._validate_acyclic(node_by_activity)
        return self

    def _validate_unique_activities(self) -> dict[UUID, ChainNode]:
        node_by_activity: dict[UUID, ChainNode] = {}
        for node in self.nodes:
            if node.activity.id in node_by_activity:
                raise ValueError(f"activity '{node.activity.fully_qualified_name}' is scheduled more than once")
            node_by_activity[node.activity.id] = node
        return node_by_activity

    def _validate_application_membership(self) -> None:
        application_by_activity: dict[UUID, Application] = {}
        for application in self.applications:
            for activity in application.activities:
                application_by_activity[activity.id] = application

        for node in self.nodes:
            if node.activity.id not in application_by_activity:
                raise ValueError(
                    f"activity '{node.activity.fully_qualified_name}' does not belong to any application of this chain"
                )

        scheduled_applications = {application_by_activity[node.activity.id].id for node in self.nodes}
        for application in self.applications:
            if application.id not in scheduled_applications:
                raise ValueError(
                    f"application '{application.fully_qualified_name}' does not contribute any activity to this chain"
                )

    def _validate_trigger_references(self, node_by_activity: dict[UUID, ChainNode]) -> None:
        for node in self.nodes:
            for predecessor in node.triggered_by:
                if predecessor.id == node.activity.id:
                    raise ValueError(f"activity '{node.activity.fully_qualified_name}' must not trigger itself")
                if predecessor.id not in node_by_activity:
                    raise ValueError(
                        f"activity '{node.activity.fully_qualified_name}' is triggered by "
                        f"'{predecessor.fully_qualified_name}' which is not part of this chain"
                    )
        if all(node.triggered_by for node in self.nodes):
            raise ValueError("chain must contain at least one root activity without predecessors")

    def _validate_acyclic(self, node_by_activity: dict[UUID, ChainNode]) -> None:
        """Reject trigger cycles, which would make the chain unschedulable."""
        unresolved = {node.activity.id: {predecessor.id for predecessor in node.triggered_by} for node in self.nodes}
        while unresolved:
            schedulable = [activity_id for activity_id, pending in unresolved.items() if not pending]
            if not schedulable:
                cycle = sorted(
                    node_by_activity[activity_id].activity.fully_qualified_name for activity_id in unresolved
                )
                raise ValueError(f"chain contains a trigger cycle between: {', '.join(cycle)}")
            for activity_id in schedulable:
                del unresolved[activity_id]
            for pending in unresolved.values():
                pending.difference_update(schedulable)

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated chain name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
