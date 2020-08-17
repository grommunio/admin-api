#include "requests.h"
#include "IOBufferOps.h"
#include "constants.h"

#include <random>
#include <chrono>

namespace exmdbpp
{

uint8_t ConnectRequest::SIDLEN = 20;
static const std::string sidchars("0123456789abcdefghjklmnopqrstvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
static std::mt19937_64 rng(ulong(std::chrono::system_clock::now().time_since_epoch().count()));

/**
 * @brief      Initialize a connection request
 */
ConnectRequest::ConnectRequest(const std::string& prefix, bool isPrivate) : prefix(prefix), isPrivate(isPrivate)
{
    sessionID.reserve(SIDLEN);
    for(uint8_t i = 0; i < SIDLEN;++i)
        sessionID += sidchars[rng()%sidchars.length()];
}

/**
 * @brief      Serialize ConnectRequest
 *
 * @param      buff  Buffer to store serialized data in
 * @param      req   Request to serialize
 *
 * @return     Reference to the buffer
 */
IOBuffer& operator<<(IOBuffer& buff, const ConnectRequest& req)
{
    buff << CallId::CONNECT << req.prefix << req.sessionID << req.isPrivate;
    return buff;
}

///////////////////////////////////////////////////////////////////////////////

LoadHierarchyTableRequest::LoadHierarchyTableRequest(const std::string& homedir, uint64_t folderId,
                                                     const std::string& username, uint8_t tableFlags) :
    homedir(homedir), folderId(folderId), username(username), tableFlags(tableFlags)
{}

/**
 * @brief      Serialize LoadHierarchyTableRequest
 *
 * @param      buff  Buffer to store serialized data in
 * @param      req   Request to serialize
 *
 * @return     Reference to the buffer
 */
IOBuffer& operator<<(IOBuffer& buff, const LoadHierarchyTableRequest& req)
{
    buff << CallId::LOAD_HIERARCHY_TABLE << req.homedir << req.folderId << !req.username.empty();
    if(!req.username.empty())
        buff << req.username;
    buff << req.tableFlags << false;
    return buff;
}

Response<LoadHierarchyTableRequest>::Response(IOBuffer& buff)
{buff >> tableId >> rowCount;}

///////////////////////////////////////////////////////////////////////////////

QueryTableRequest::QueryTableRequest(const std::string& homedir, const std::string& username, uint32_t cpid, uint32_t tableId,
                                     const std::vector<uint32_t>& proptags, uint32_t startPos, uint32_t rowNeeded) :
    homedir(homedir), username(username), cpid(cpid), tableId(tableId), proptags(proptags), startPos(startPos),
    rowNeeded(rowNeeded)
{}

/**
 * @brief      Serialize QueryTableRequest
 *
 * @param      buff  Buffer to store serialized data in
 * @param      req   Request to serialize
 *
 * @return     Reference to the buffer
 */
IOBuffer& operator<<(IOBuffer& buff, const QueryTableRequest& req)
{
    buff << CallId::QUERY_TABLE << req.homedir << !req.username.empty();
    if(!req.username.empty())
        buff << req.username;
    buff << req.cpid << req.tableId << uint16_t(req.proptags.size());
    for(uint32_t proptag : req.proptags)
        buff << proptag;
    buff << req.startPos << req.rowNeeded;
    return buff;
}

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

///////////////////////////////////////////////////////////////////////////////

UnloadTableRequest::UnloadTableRequest(const std::string& homedir, uint32_t tableId) : homedir(homedir), tableId(tableId)
{}

/**
 * @brief      Serialize UnloadTableRequest
 *
 * @param      buff  Buffer to store serialized data in
 * @param      req   Request to serialize
 *
 * @return     Reference to the buffer
 */
IOBuffer& operator<<(IOBuffer& buff, const UnloadTableRequest& req)
{
    buff << CallId::UNLOAD_TABLE << req.homedir << req.tableId;
    return buff;
}

}
