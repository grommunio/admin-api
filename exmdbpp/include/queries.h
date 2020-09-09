#pragma once

#include <vector>

#include "requests.h"
#include "ExmdbClient.h"

namespace exmdbpp
{


/**
 * @brief   Collection of multiple-request queries
 */
namespace queries
{

/**
 * @brief      Response interpreter for ExmdbQueries::getFolderList
 *
 * Utility class providing a more structured access to data returned by
 * ExmdbQueries::getFolderList.
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
 * @brief      Response interpreter for ExmdbQueries::getFolderOwnerList
 *
 * Utility class providing a more structured access to data returned by
 * ExmdbQueries::getPublicFolderOwnerList.
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

/**
 * @brief      ExmdbClient extension providing useful queries
 *
 * ExmdbQueries can be used as a substitute for ExmdbClient and provides
 * implementations of frequently used queries (i.e. requests with fixed
 * default values or queries consisting of multiple requests.
 */
class ExmdbQueries final: public ExmdbClient
{
public:
    using ExmdbClient::ExmdbClient;

    requests::Response<requests::QueryTableRequest> getFolderList(const std::string&);
    requests::Response<requests::CreateFolderByPropertiesRequest> createPublicFolder(const std::string&, uint32_t, const std::string&, const std::string&, const std::string&);
    requests::SuccessResponse deletePublicFolder(const std::string&, uint64_t);
    requests::Response<requests::QueryTableRequest> getPublicFolderOwnerList(const std::string&, uint64_t);
    requests::NullResponse addFolderOwner(const std::string&, uint64_t, const std::string&);
    requests::NullResponse deleteFolderOwner(const std::string&, uint64_t, uint64_t);
    requests::Response<requests::SetStorePropertiesRequest> setStoreProperties(const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);
    requests::NullResponse unloadStore(const std::string&);
};

}

}
