#pragma once

#include "requests.h"

namespace exmdbpp
{
class ExmdbClient;

namespace queries
{

Response<QueryTableRequest> getFolderList(ExmdbClient&, const std::string&);

}

}
