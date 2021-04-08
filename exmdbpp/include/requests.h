#pragma once

#include <string>
#include <vector>

#include "structures.h"

namespace exmdbpp
{

class IOBuffer;

/**
 * @brief   RPC requests and responses
 */
namespace requests
{

/**
 * @brief   Empty response
 */
struct NullResponse
{
    NullResponse() = default;
    NullResponse(IOBuffer&);

};

/**
 * @brief      Template to handle empty response.
 *
 * @tparam     Request  Request that triggered the response.
 */
template<class Request>
struct Response final : NullResponse
{
using NullResponse::NullResponse;
};

/**
 * @brief      Request to Response sype mapping struct
 *
 * Allows reuse of Response classes by explicitely mapping Requests to specific
 * Response classes.
 *
 * The default is to map each Request to its own Response specialization (or
 * the generic, empty, response if no specialization is provided).
 */
template<class Request>
struct response_map
{using type = Response<Request>;};

/**
 * @brief      Do not perform any response interpretation
 *
 * @param      <unnamed>  Buffer to read from (unused)
 */
inline NullResponse::NullResponse(IOBuffer&)
{}

/**
 * @brief      Stream insertion operator overload for IOBuffer
 *
 * @param      buffer   Buffer to write data to
 * @param      req      Request to serialize
 *
 * @tparam     Request  Type of the request
 *
 * @return     Reference to the buffer
 */
template<class Request>
inline IOBuffer& operator<<(IOBuffer& buffer, const Request& req)
{
    req.serialize(buffer);
    return buffer;
}

/**
 * @brief      Generic response for requests returning only success status
 */
struct SuccessResponse
{
    SuccessResponse() = default;
    SuccessResponse(IOBuffer&);

    bool success;
};

/**
 * @brief       Generic response containing a list of problems
 *
 * Usually returned by requests that set properties.
 */
struct ProblemsResponse
{
    ProblemsResponse() = default;
    ProblemsResponse(IOBuffer&);

    std::vector<structures::PropertyProblem> problems; ///< List of problems that occured when setting store values
};

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

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, bool, const std::string& = mkSessionID());

private:
    static std::string mkSessionID();
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void ConnectRequest::serialize(IOBuffer& buff) const
{serialize(buff, prefix, isPrivate, sessionID);}

///////////////////////////////////////////////////////////////////////////////

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

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint64_t, const std::string&, uint8_t);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void LoadHierarchyTableRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, folderId, username, tableFlags);}

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

///////////////////////////////////////////////////////////////////////////////

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

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, const std::string&, uint32_t, uint32_t, const std::vector<uint32_t>&, uint32_t, uint32_t);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void QueryTableRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, username, cpid, tableId, proptags, startPos, rowNeeded);}

/**
 * @brief      Response specialization for QueryTableRequest
 */
template<>
struct Response<QueryTableRequest>
{
    Response() = default;
    Response(IOBuffer&);

    std::vector<std::vector<structures::TaggedPropval> > entries; ///< Returned rows of entries
};

///////////////////////////////////////////////////////////////////////////////

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

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void UnloadTableRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, tableId);}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Change number allocation request
 */
struct AllocateCnRequest
{
    AllocateCnRequest(const std::string&);

    std::string homedir;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void AllocateCnRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir);}

/**
 * @brief      Response specialization for AllocateCnRequest
 */
template<>
struct Response<AllocateCnRequest>
{
    Response(IOBuffer&);

    uint64_t changeNum; ///< Newly allocated change number
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Create folder defined by list of properties
 */
struct CreateFolderByPropertiesRequest
{
    CreateFolderByPropertiesRequest(const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);

    std::string homedir;
    uint32_t cpid;
    std::vector<structures::TaggedPropval> propvals;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void CreateFolderByPropertiesRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, cpid, propvals);}

/**
 * @brief      Response specialization for CreateFolderByPropertiesRequest
 */
template<>
struct Response<CreateFolderByPropertiesRequest>
{
    Response() = default;
    Response(IOBuffer&);

    uint64_t folderId; ///< ID of the newly cerated folder
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Delete folder
 */
struct DeleteFolderRequest
{
    DeleteFolderRequest(const std::string&, uint32_t, uint64_t, bool);

    std::string homedir;
    uint32_t cpid;
    uint64_t folderId;
    bool hard;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t, uint64_t, bool);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void DeleteFolderRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, cpid, folderId, hard);}

/**
 * Response type override for delete folder request (-> SuccessResponse)
 */
template<>
struct response_map<DeleteFolderRequest>
{using type = SuccessResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Load folder permission table
 */
struct LoadPermissionTableRequest
{
    LoadPermissionTableRequest(const std::string&, uint64_t, uint8_t=0);

    std::string homedir;
    uint64_t folderId;
    uint8_t tableFlags;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint64_t, uint8_t=0);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void LoadPermissionTableRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, folderId, tableFlags);}

/**
 * @brief      Response specialization for LoadPermissionTableRequest
 */
template<>
struct Response<LoadPermissionTableRequest>
{
    Response(IOBuffer&);

    uint32_t tableId;   ///< ID of the created view
    uint32_t rowCount;  ///< Number of rows in the view
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Update folder permissions
 */
struct UpdateFolderPermissionRequest
{
    UpdateFolderPermissionRequest(const std::string&, uint64_t, bool, const std::vector<structures::PermissionData>&);

    const std::string& homedir;
    uint64_t folderId;
    bool freebusy;
    std::vector<structures::PermissionData> permissions;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint64_t, bool, const std::vector<structures::PermissionData>&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void UpdateFolderPermissionRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, folderId, freebusy, permissions);}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Update store properties
 */
struct SetStorePropertiesRequest
{
    SetStorePropertiesRequest(const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);

    std::string homedir;
    uint32_t cpid;
    std::vector<structures::TaggedPropval> propvals;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void SetStorePropertiesRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, cpid, propvals);}

/**
 * Response type override for set store properties request (-> ProblemsResponse)
 */
template<>
struct response_map<SetStorePropertiesRequest>
{using type = ProblemsResponse;};


///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Unload store
 */
struct UnloadStoreRequest
{
    UnloadStoreRequest(const std::string&);

    std::string homedir;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void UnloadStoreRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir);}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief       Set folder properties
 */
struct SetFolderPropertiesRequest
{
    SetFolderPropertiesRequest(const std::string&, uint32_t, uint64_t, const std::vector<structures::TaggedPropval>&);

    std::string homedir;
    uint32_t cpid;
    uint64_t folderId;
    std::vector<structures::TaggedPropval> propvals;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t, uint64_t, const std::vector<structures::TaggedPropval>&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void SetFolderPropertiesRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, cpid, folderId, propvals);}

/**
 * Response type override for set folder properties request (-> ProblemsResponse)
 */
template<>
struct response_map<SetFolderPropertiesRequest>
{using type = ProblemsResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief       Get folder properties
 */
struct GetFolderPropertiesRequest
{
    GetFolderPropertiesRequest(const std::string&, uint32_t, uint64_t, const std::vector<uint32_t>&);

    std::string homedir;
    uint32_t cpid;
    uint64_t folderId;
    std::vector<uint32_t> proptags;

    void serialize(IOBuffer&) const;
    static void serialize(IOBuffer&, const std::string&, uint32_t, uint64_t, const std::vector<uint32_t>&);
};

/**
 * @brief      Serialize request
 *
 * @param      buff  Buffer to write data to
 */
inline void GetFolderPropertiesRequest::serialize(IOBuffer& buff) const
{serialize(buff, homedir, cpid, folderId, proptags);}

/**
 * @brief      Response specialization for GetFolderPropertiesRequest
 */
template<>
struct Response<GetFolderPropertiesRequest>
{
    Response() = default;
    Response(IOBuffer&);

    std::vector<structures::TaggedPropval> propvals;
};

}

}
