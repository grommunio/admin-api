#include "requests.h"
#include "IOBufferOps.h"
#include "constants.h"

#include <random>
#include <chrono>

using namespace exmdbpp::structures;
using namespace exmdbpp::constants;

namespace exmdbpp::requests
{

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
SuccessResponse::SuccessResponse(IOBuffer& buff) : success(buff.pop<uint8_t>())
{}

///////////////////////////////////////////////////////////////////////////////

uint8_t ConnectRequest::SIDLEN = 15;
static const std::string sidchars("0123456789abcdefghjklmnopqrstvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
static std::mt19937_64 rng(ulong(std::chrono::system_clock::now().time_since_epoch().count()));

/**
 * @brief      Initialize a connection request
 */
ConnectRequest::ConnectRequest(const std::string& prefix, bool isPrivate) :
    prefix(prefix),
    sessionID(mkSessionID()),
    isPrivate(isPrivate)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void ConnectRequest::serialize(IOBuffer& buff, const std::string& prefix, bool isPrivate, const std::string& sessionID)
{buff << CallId::CONNECT << prefix << sessionID << isPrivate;}

/**
 * @brief      Generate session ID
 *
 * Creates a random session ID string of length SIDLEN.
 *
 * @return     String containing the sessionID
 */
std::string ConnectRequest::mkSessionID()
{
    std::string sessionID;
    sessionID.reserve(SIDLEN);
    for(uint8_t i = 0; i < SIDLEN;++i)
        sessionID += sidchars[rng()%sidchars.length()];
    return sessionID;
}
///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize load hierarchy table request
 */
LoadHierarchyTableRequest::LoadHierarchyTableRequest(const std::string& homedir, uint64_t folderId,
                                                     const std::string& username, uint8_t tableFlags) :
    homedir(homedir), folderId(folderId), username(username), tableFlags(tableFlags)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void LoadHierarchyTableRequest::serialize(IOBuffer& buff, const std::string& homedir, uint64_t folderId,
                                          const std::string& username, uint8_t tableFlags)
{
    buff << CallId::LOAD_HIERARCHY_TABLE << homedir << folderId << !username.empty();
    if(!username.empty())
        buff << username;
    buff << tableFlags << false;
}

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
Response<LoadHierarchyTableRequest>::Response(IOBuffer& buff)
{buff >> tableId >> rowCount;}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize query table request
 */
QueryTableRequest::QueryTableRequest(const std::string& homedir, const std::string& username, uint32_t cpid, uint32_t tableId,
                                     const std::vector<uint32_t>& proptags, uint32_t startPos, uint32_t rowNeeded) :
    homedir(homedir), username(username), cpid(cpid), tableId(tableId), proptags(proptags), startPos(startPos),
    rowNeeded(rowNeeded)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void QueryTableRequest::serialize(IOBuffer& buff, const std::string& homedir, const std::string& username, uint32_t cpid,
                                  uint32_t tableId,const std::vector<uint32_t>& proptags, uint32_t startPos, uint32_t rowNeeded)
{
    buff << CallId::QUERY_TABLE << homedir << !username.empty();
    if(!username.empty())
        buff << username;
    buff << cpid << tableId << uint16_t(proptags.size());
    for(uint32_t proptag : proptags)
        buff << proptag;
    buff << startPos << rowNeeded;
}

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
Response<QueryTableRequest>::Response(IOBuffer& buff)
{
    entries.resize(buff.pop<uint32_t>());
    for(auto& entry : entries)
    {
        uint16_t count = buff.pop<uint16_t>();
        entry.reserve(count);
        for(uint16_t i = 0; i < count; ++i)
            entry.emplace_back(buff);
    }
}

/**
 * @brief      Initialize unload table request
 */
UnloadTableRequest::UnloadTableRequest(const std::string& homedir, uint32_t tableId) : homedir(homedir), tableId(tableId)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void UnloadTableRequest::serialize(IOBuffer& buff, const std::string& homedir, uint32_t tableId)
{buff << CallId::UNLOAD_TABLE << homedir << tableId;}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize change number allocation request
 */

AllocateCnRequest::AllocateCnRequest(const std::string& homedir) : homedir(homedir)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void AllocateCnRequest::serialize(IOBuffer& buff, const std::string& homedir)
{buff << CallId::ALLOCATE_CN << homedir;}


/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
Response<AllocateCnRequest>::Response(IOBuffer& buff) : changeNum(buff.pop<uint64_t>())
{}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize folder creation request
 */
CreateFolderByPropertiesRequest::CreateFolderByPropertiesRequest(const std::string& homedir, uint32_t cpid,
                                                                 const std::vector<TaggedPropval>& propvals)
    : homedir(homedir), cpid(cpid), propvals(propvals)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void CreateFolderByPropertiesRequest::serialize(IOBuffer& buff, const std::string& homedir, uint32_t cpid,
                                                const std::vector<TaggedPropval>& propvals)
{
    buff << CallId::CREATE_FOLDER_BY_PROPERTIES << homedir << cpid << uint16_t(propvals.size());
    for(const TaggedPropval& propval : propvals)
        propval.serialize(buff);
}

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
Response<CreateFolderByPropertiesRequest>::Response(IOBuffer& buff) : folderId(buff.pop<uint64_t>())
{}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize folder deletion request
 */
DeleteFolderRequest::DeleteFolderRequest(const std::string& homedir, uint32_t cpid, uint64_t folderId, bool hard)
    : homedir(homedir), cpid(cpid), folderId(folderId), hard(hard)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void DeleteFolderRequest::serialize(IOBuffer& buff, const std::string& homedir, uint32_t cpid, uint64_t folderId, bool hard)
{buff << CallId::DELETE_FOLDER << homedir << cpid << folderId << hard;}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize load permission table request
 */
LoadPermissionTableRequest::LoadPermissionTableRequest(const std::string& homedir, uint64_t folderId, uint8_t tableFlags)
    : homedir(homedir), folderId(folderId), tableFlags(tableFlags)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void LoadPermissionTableRequest::serialize(IOBuffer& buff, const std::string& homedir, uint64_t folderId, uint8_t tableFlags)
{buff << CallId::LOAD_PERMISSION_TABLE << homedir << folderId << tableFlags;}

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the data
 */
Response<LoadPermissionTableRequest>::Response(IOBuffer& buff) : tableId(buff.pop<uint32_t>()), rowCount(buff.pop<uint32_t>())
{}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize update folder permission request
 */
UpdateFolderPermissionRequest::UpdateFolderPermissionRequest(const std::string& homedir, uint64_t folderId, bool freebusy,
                                                             const std::vector<structures::PermissionData>& permissions)
    : homedir(homedir), folderId(folderId), freebusy(freebusy), permissions(permissions)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void UpdateFolderPermissionRequest::serialize(IOBuffer& buff, const std::string& homedir, uint64_t folderId, bool freebusy,
                                              const std::vector<structures::PermissionData>& permissions)
{
    buff << CallId::UPDATE_FOLDER_PERMISSION << homedir << folderId << freebusy << uint16_t(permissions.size());
    for(auto& permissionData : permissions)
        permissionData.serialize(buff);
}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize store update request
 */
SetStorePropertiesRequest::SetStorePropertiesRequest(const std::string& homedir, uint32_t cpid,
                                                     const std::vector<structures::TaggedPropval>& propvals)
    : homedir(homedir), cpid(cpid), propvals(propvals)
{}

/**
 * @brief      Write serialized request data to buffer
 *
 * @param      buff       Buffer to write to
 */
void SetStorePropertiesRequest::serialize(IOBuffer& buff, const std::string& homedir, uint32_t cpid,
                                          const std::vector<structures::TaggedPropval>& propvals)
{
    buff << CallId::SET_STORE_PROPERTIES << homedir << cpid << uint16_t(propvals.size());
    for(const TaggedPropval& propval : propvals)
        propval.serialize(buff);
}

/**
 * @brief      Deserialize store update response
 *
 * @param     buff      Buffer containing the response
 */
Response<SetStorePropertiesRequest>::Response(IOBuffer& buff)
{
    size_t count = buff.pop<uint16_t>();
    problems.reserve(count);
    for(size_t i = 0; i < count; ++i)
        problems.emplace_back(buff);
}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize unload store request
 */
UnloadStoreRequest::UnloadStoreRequest(const std::string& homedir) : homedir(homedir)
{}

/**
 * @brief      Deserialize store update response
 *
 * @param     buff      Buffer containing the response
 */
void UnloadStoreRequest::serialize(IOBuffer& buff, const std::string& homedir)
{buff << CallId::UNLOAD_STORE << homedir;}

}
