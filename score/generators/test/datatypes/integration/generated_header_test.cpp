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
#include "example/Types/Double.h"
#include "example/Types/Float.h"
#include "example/Types/Int16.h"
#include "example/Types/Int32.h"
#include "example/Types/Int64.h"
#include "example/Types/Int8.h"
#include "example/Types/PublicCount.h"
#include "example/Types/Text.h"
#include "example/Types/UInt16.h"
#include "example/Types/UInt32.h"
#include "example/Types/UInt64.h"
#include "example/Types/UInt8.h"

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

int main()
{
    example::Types::Bool enabled{true};
    example::Types::PublicCount count{7};
    example::Types::Text text{"ready"};
    return enabled && count == 7 && text == "ready" ? 0 : 1;
}