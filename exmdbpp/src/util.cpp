/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020 grommunio GmbH
 */
#include <endian.h>
#include <ctime>

#include "util.h"

namespace exmdbpp::util
{

static const uint16_t endianHelper = 0x0100;
static bool isBigEndian = bool(*reinterpret_cast<const uint8_t*>(&endianHelper)); ///< Determine whether current machine uses big endian


uint64_t valueToGc(uint64_t value)
{return htobe64(value&0x0000FFFFFFFFFFFF) << (isBigEndian? 16 : 0);}

uint64_t makeEid(uint16_t replid, uint64_t gc)
{return replid | gc;}

uint64_t makeEidEx(uint16_t replid, uint64_t value)
{return makeEid(replid, valueToGc(value));}

/**
 * @brief      Convert Windows NT timestamp to UNIX timestamp
 *
 * @param      ntTime  Windows NT timestamp
 *
 * @return     UNIX timestamp
 */
time_t nxTime(uint64_t ntTime)
{return ntTime/10000000-11644473600;}

/**
 * @brief      Convert UNIX timestamp to Windows NT timestamp
 *
 * @param      nxTime  UNIX timestamp
 *
 * @return     Windows NT timestamp
 */
uint64_t ntTime(time_t nxTime)
{return (uint64_t(nxTime+11644473600))*10000000;}

}
