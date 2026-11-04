/*******************************************************************************
 * Copyright (c) 2026 Contributors to the Eclipse Foundation
 *
 * See the NOTICE file(s) distributed with this work for additional
 * information regarding copyright ownership.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Apache License Version 2.0 which is available at
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * SPDX-License-Identifier: Apache-2.0
 *******************************************************************************/

#include "example/Types/Bool.h"
#include "example/Types/Count.h"
#include "example/Types/CurrentState.h"
#include "example/Types/Double.h"
#include "example/Types/Float.h"
#include "example/Types/Int16.h"
#include "example/Types/Int16Mode.h"
#include "example/Types/Int32.h"
#include "example/Types/Int32Mode.h"
#include "example/Types/Int64.h"
#include "example/Types/Int64Mode.h"
#include "example/Types/Int8.h"
#include "example/Types/Int8Mode.h"
#include "example/Types/PublicCount.h"
#include "example/Types/PublicMode.h"
#include "example/Types/PublicState.h"
#include "example/Types/Text.h"
#include "example/Types/UInt16.h"
#include "example/Types/UInt16Mode.h"
#include "example/Types/UInt32.h"
#include "example/Types/UInt32Mode.h"
#include "example/Types/UInt64.h"
#include "example/Types/UInt64Mode.h"
#include "example/Types/UInt8.h"
#include "example/Types/UInt8Mode.h"

#include <type_traits>

static_assert(std::is_same_v<example::Types::Bool, bool>);
static_assert(std::is_same_v<example::Types::Float, float>);
static_assert(std::is_same_v<example::Types::Double, double>);
static_assert(std::is_same_v<example::Types::Text, std::string>);
static_assert(std::is_same_v<example::Types::Int8, std::int8_t>);
static_assert(std::is_same_v<example::Types::Int16, std::int16_t>);
static_assert(std::is_same_v<example::Types::Int32, std::int32_t>);
static_assert(std::is_same_v<example::Types::Int64, std::int64_t>);
static_assert(std::is_same_v<example::Types::UInt8, std::uint8_t>);
static_assert(std::is_same_v<example::Types::UInt16, std::uint16_t>);
static_assert(std::is_same_v<example::Types::UInt32, std::uint32_t>);
static_assert(std::is_same_v<example::Types::UInt64, std::uint64_t>);
static_assert(std::is_same_v<example::Types::Count, example::Types::UInt16>);
static_assert(std::is_same_v<example::Types::PublicCount, example::Types::Count>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::Int8Mode>, std::int8_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::Int16Mode>, std::int16_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::Int32Mode>, std::int32_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::Int64Mode>, std::int64_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::UInt8Mode>, std::uint8_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::UInt16Mode>, std::uint16_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::UInt32Mode>, std::uint32_t>);
static_assert(std::is_same_v<std::underlying_type_t<example::Types::UInt64Mode>, std::uint64_t>);
static_assert(std::is_same_v<example::Types::PublicMode, example::Types::Int8Mode>);
static_assert(!std::is_convertible_v<example::Types::PublicMode, std::int8_t>);
static_assert(std::is_aggregate_v<example::Types::State>);
static_assert(std::is_same_v<example::Types::PublicState, example::Types::State>);
static_assert(std::is_same_v<decltype(example::Types::State::enabled), bool>);
static_assert(std::is_same_v<decltype(example::Types::State::text), std::string>);
static_assert(std::is_same_v<decltype(example::Types::State::count), example::Types::Count>);
static_assert(std::is_same_v<decltype(example::Types::State::mode), example::Types::Int8Mode>);
static_assert(std::is_same_v<decltype(example::Types::State::version), example::Shared::Version>);
static_assert(std::is_same_v<example::Types::State::version_generated_type, example::Shared::Version>);
static_assert(std::is_aggregate_v<example::Types::CurrentState>);
static_assert(!std::is_base_of_v<example::Types::State, example::Types::CurrentState>);
static_assert(std::is_same_v<decltype(example::Types::CurrentState::sequence), std::uint32_t>);
static_assert(std::is_same_v<decltype(example::Types::CurrentState::version), example::Shared::Version>);
static_assert(std::is_same_v<example::Types::CurrentState::count_generated_type, example::Types::Count>);
static_assert(std::is_same_v<example::Types::CurrentState::mode_generated_type, example::Types::Int8Mode>);

int main()
{
    example::Types::Bool enabled{true};
    example::Types::PublicCount count{7};
    example::Types::Text text{"ready"};
    const auto mode = example::Types::PublicMode::Maximum;
    const auto signed_mode = example::Types::Int8Mode::Minimum;
    const auto wide_mode = example::Types::UInt16Mode::Maximum;
    const example::Types::PublicState state{enabled, text, count, mode, example::Shared::Version{1, 2}};
    const example::Types::CurrentState current{9, enabled, text, count, mode, example::Shared::Version{3, 4}};
    return enabled && count == 7 && text == "ready" && static_cast<std::int8_t>(mode) == 1 &&
                   static_cast<std::int8_t>(signed_mode) == -1 && static_cast<std::uint16_t>(wide_mode) == 1 &&
                   state.enabled && state.text == "ready" && state.count == 7 && state.mode == mode &&
                   state.version.major == 1 && state.version.minor == 2 && current.sequence == 9 &&
                   current.enabled && current.text == "ready" && current.count == 7 && current.mode == mode &&
                   current.version.major == 3 && current.version.minor == 4
               ? 0
               : 1;
}