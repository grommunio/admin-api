#pragma once

#include <vector>

#include "requests.h"

namespace exmdbpp
{
class ExmdbClient;


/**
 * @brief   Collection of multiple-request queries
 */
namespace queries
{

/**
 * @brief      Interpreter class for getFolderList response
 *
 * Utility class providing a more structured access to data returned by
 * getFolderList.
 */
struct FolderListResponse
{
    struct Folder
    {
        uint64_t folderId = 0;
        std::string displayName;
        std::string comment;
        uint64_t creationTime = 0;
    };

    FolderListResponse(const requests::Response<requests::QueryTableRequest>&);

    std::vector<Folder> folders;
};


/**
 * @brief      Interpreter class for getFolderOwnerList response
 *
 * Utility class providing a more structured access to data returned by
 * getPublicFolderOwnerList.
 */
struct FolderOwnerListResponse
{
    struct Owner
    {
        uint64_t memberId = 0;
        std::string memberName;
        uint32_t memberRights = 0;
    };

    FolderOwnerListResponse(const requests::Response<requests::QueryTableRequest>&);

    std::vector<Owner> owners;
};

requests::Response<requests::QueryTableRequest> getFolderList(ExmdbClient&, const std::string&);
requests::Response<requests::CreateFolderByPropertiesRequest> createPublicFolder(ExmdbClient&, const std::string&, uint32_t, const std::string&, const std::string&, const std::string&);
requests::SuccessResponse deletePublicFolder(ExmdbClient&, const std::string&, uint64_t);
requests::Response<requests::QueryTableRequest> getPublicFolderOwnerList(ExmdbClient&, const std::string&, uint64_t);
requests::NullResponse addFolderOwner(ExmdbClient&, const std::string&, uint64_t, const std::string&);
requests::NullResponse deleteFolderOwner(ExmdbClient&, const std::string&, uint64_t, uint64_t);
requests::Response<requests::SetStorePropertiesRequest> setStoreProperties(ExmdbClient&, const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);

}

}
