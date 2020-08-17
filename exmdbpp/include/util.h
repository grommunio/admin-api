#pragma once

#include <cstdint>
#include <ctime>

namespace exmdbpp::util
{

uint64_t valueToGc(uint64_t);
uint64_t makeEid(uint16_t, uint64_t);
uint64_t makeEidEx(uint16_t, uint64_t);
time_t nxTime(uint64_t);

}
