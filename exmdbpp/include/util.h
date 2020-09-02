#pragma once

#include <cstdint>
#include <ctime>

#include "structures.h"

namespace exmdbpp::util
{

uint64_t valueToGc(uint64_t);
uint64_t makeEid(uint16_t, uint64_t);
uint64_t makeEidEx(uint16_t, uint64_t);
time_t nxTime(uint64_t);
uint64_t ntTime(time_t=time(nullptr));

}
