#pragma once

#include <string>
#include <vector>

 #include "structures.h"

namespace exmdbpp
{

class IOBuffer;

/**
 * @brief      Template to handle empty response.
 *
 * @tparam     Request  Request that triggered the response.
 */
template<class Request>
struct Response
{
    Response() = default;
    Response(IOBuffer&);
};

/**
 * @brief      Do not perform any response interpretation
 *
 * @param      <unnamed>  Buffer to read from (unused)
 *
 * @tparam     Request    Request the response was triggered by
 */
template<class Request>
inline Response<Request>::Response(IOBuffer&)
{}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Connection request
 */
struct ConnectRequest
{
    ConnectRequest(const std::string&, bool);

    std::string prefix;     ///< Data area prefix managed by the server
    std::string sessionID;  ///< [TODO]: Find out what this is used for
    bool isPrivate;         ///< Whether private or public data is accessed

    static uint8_t SIDLEN;  ///< Number of charaters to use for session ID
};

IOBuffer& operator<<(IOBuffer&, const ConnectRequest&);

/**
 * @brief      Load hierarchy table request
 *
 * Requests creation of a table view which can then be queries using QueryTableRequest.
 * The created table must be explicitely discarded with an UnloadTableRequest.
 */
struct LoadHierarchyTableRequest
{
    LoadHierarchyTableRequest(const std::string&, uint64_t, const std::string&, uint8_t);

    std::string homedir;    ///< Home directory of the domain
    uint64_t folderId;      ///< ID of the folder to view
    std::string username;   ///< [TODO] Find out what this is used for
    uint8_t tableFlags;     ///< [TODO] Find out what this is used for
};

IOBuffer& operator<<(IOBuffer&, const LoadHierarchyTableRequest&);

/**
 * @brief      Response specialization for LoadHierarchyTableRequest
 */
template<>
struct Response<LoadHierarchyTableRequest>
{
    Response(IOBuffer&);

    uint32_t tableId;   ///< ID of the created view
    uint32_t rowCount;  ///< Number of rows in the view
};

/**
 * @brief      Query table request
 *
 * Used to load data from a table created with LoadHierarchyTableRequest.
 */
struct QueryTableRequest
{
    QueryTableRequest(const std::string&, const std::string&, uint32_t, uint32_t, const std::vector<uint32_t>&, uint32_t, uint32_t);

    std::string homedir;
    std::string username;
    uint32_t cpid;
    uint32_t tableId;
    std::vector<uint32_t> proptags;
    uint32_t startPos;
    uint32_t rowNeeded;
};

IOBuffer& operator<<(IOBuffer&, const QueryTableRequest&);

/**
 * @brief      Response specialization for QueryTableRequest
 */
template<>
struct Response<QueryTableRequest>
{
    Response() = default;
    Response(IOBuffer&);

    std::vector<std::vector<TaggedPropval> > entries;
};

/**
 * @brief      Unload table request
 *
 * Discard view previously created with LoadHierarchyTableRequest.
 */
struct UnloadTableRequest
{
    UnloadTableRequest(const std::string&, uint32_t);

    std::string homedir;
    uint32_t tableId;
};

IOBuffer& operator<<(IOBuffer&, const UnloadTableRequest&);

}
