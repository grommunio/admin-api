#pragma once

#include "requests.h"

namespace exmdbpp
{
class ExmdbClient;

namespace queries
{

Response<QueryTableRequest> getFolderList(ExmdbClient&, const std::string&);
Response<CreateFolderByPropertiesRequest> createPublicFolder(ExmdbClient&, const std::string&, uint32_t, const std::string&, const std::string&, const std::string&);

}

}
