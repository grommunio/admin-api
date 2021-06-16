#pragma once

#include <string>
#include <vector>
#include <array>
#include <limits>
#include <stdexcept>
#include <string>

#include "constants.h"
#include "structures.h"
#include "IOBuffer.h"

namespace exmdbpp
{

/**
 * @brief      Convenience container interface
 *
 * Provides a simple interface for serializing arrays of objects.
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 */
template<typename SizeType, typename T>
class Collection
{
public:
    Collection(const std::vector<T>&) noexcept;
    template<size_t N> constexpr Collection(const std::array<T, N>&) noexcept;
    template<size_t N> constexpr Collection(const T(&)[N]) noexcept;

    using value_type = T; ///< Type of contained values
    using iterator = const T*; ///< Iterator type
    using const_iterator = const T*; ///< Const iterator type

    iterator begin() const noexcept;
    iterator end() const noexcept;
    size_t size() const noexcept;
private:
    const T *b, *e; ///< Beginning and end
};

/**
 * @brief      Construct from vector
 *
 * @param      data      The data
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 */
template<typename SizeType, typename T>
inline Collection<SizeType, T>::Collection(const std::vector<T>& data) noexcept : b(data.data()), e(data.data()+data.size())
{}


/**
 * @brief      Construct from array
 *
 * If array size is bigger than the maximum value supported by SizeType,
 * a compile time error is raised.
 *
 * @param      data      The data
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 * @tparam     N         Array length
 */
template<typename SizeType, typename T>
template<size_t N>
inline constexpr Collection<SizeType, T>::Collection(const std::array<T, N>& data) noexcept
    : b(data.begin()), e(data.end())
{static_assert (N <= std::numeric_limits<SizeType>::max(), "SizeType is to small to encode array length");}

/**
 * @brief      Construct from C-style array
 *
 * If array size is bigger than the maximum value supported by SizeType,
 * a compile time error is raised.
 *
 * @param      data      The data
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 * @tparam     N         Array length
 */
template<typename SizeType, typename T>
template<size_t N>
inline constexpr Collection<SizeType, T>::Collection(const T (&data)[N]) noexcept : b(data), e(data+N)
{static_assert (N <= std::numeric_limits<SizeType>::max(), "SizeType is to small to encode array length");}

/**
 * @brief      Return iterator to beginning
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 *
 * @return     Iterator to the first element
 */
template<typename SizeType, typename T>
inline auto Collection<SizeType, T>::begin() const noexcept -> iterator
{return b;}

/**
 * @brief      Return iterator to end
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 *
 * @return     Iterator to element following the last element
 */
template<typename SizeType, typename T>
inline auto Collection<SizeType, T>::end() const noexcept -> iterator
{return e;}

/**
 * @brief      Return size of collection
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 *
 * @return     Number of elements
 */
template<typename SizeType, typename T>
inline size_t Collection<SizeType, T>::size() const noexcept
{return e-b;}

/**
 * @brief      IOBuffer::Serialize specialization for Collection
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 */
template<typename SizeType, typename T>
struct IOBuffer::Serialize<Collection<SizeType, T>>
{static void push(IOBuffer&, const Collection<SizeType, T>&);};

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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
    explicit NullResponse(IOBuffer&);
};

/**
 * @brief      Template to handle empty response.
 *
 * @tparam     Request  Request that triggered the response.
 */
template<uint8_t CallId>
struct Response final : NullResponse
{using NullResponse::NullResponse;};

/**
 * @brief      Request ID to Response type mapping struct
 *
 * Allows reuse of Response classes by explicitely mapping Requests to specific
 * Response classes.
 *
 * The default is to map each Request to its own Response specialization (or
 * the generic (empty) response if no specialization is provided).
 */
template<uint8_t CallId>
struct response_map
{using type = Response<CallId>;};

/// Response type resolution alias (by request)
template<class Request>
using Response_t = typename response_map<Request::callId>::type;

/// Response type resolution alias (by request ID)
template<uint8_t CallId>
using Response_i = typename response_map<CallId>::type;


/**
 * @brief      Do not perform any response interpretation
 *
 * Success of request is checked via return code on message reception by client
 *
 * @param      <unnamed>  Buffer to read from (unused)
 */
inline NullResponse::NullResponse(IOBuffer&)
{}

/**
 * @brief   Load table response
 *
 * Result of LoadHierarchyTableRequest or LoadPermissionTableRequest
 */
struct LoadTableResponse
{
    explicit LoadTableResponse(IOBuffer&);

    uint32_t tableId;   ///< ID of the created view
    uint32_t rowCount;  ///< Number of rows in the view
};


/**
 * @brief       Generic response containing a list of problems
 *
 * Usually returned by requests that set properties.
 */
struct ProblemsResponse
{
    ProblemsResponse() = default;
    explicit ProblemsResponse(IOBuffer&);

    std::vector<structures::PropertyProblem> problems; ///< List of problems that occured when setting store values
};

/**
 * @brief      Generic response containing a list of tagged propvals
 */
struct PropvalResponse
{
    PropvalResponse() = default;
    explicit PropvalResponse(IOBuffer&);

    std::vector<structures::TaggedPropval> propvals; ///< Propvals genereated by the request
};

/**
 * @brief      Generic response for requests returning only success status
 */
struct SuccessResponse
{
    SuccessResponse() = default;
    explicit SuccessResponse(IOBuffer&);

    bool success; ///< Whether the operation was successful
};

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


/**
 * @brief      Request template
 *
 * @tparam     CallId  ID of the RPC call
 * @tparam     Args    RPC signature
 */
template<uint8_t CallId, typename... Args>
struct Request
{
    static void write(IOBuffer&, const Args&...);

    static constexpr uint8_t callId = CallId;
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Change number allocation request
 *
 * @param   string  homedir
 *
 * @return  Response<AllocateCnRequest::callId>
 */
struct AllocateCnRequest : public Request<constants::CallId::ALLOCATE_CN, std::string> {};

template<>
struct Response<AllocateCnRequest::callId>
{
    explicit Response(IOBuffer&);

    uint64_t changeNum; ///< Newly allocated change number
};


//////////////////////////////////////////////////////////////////////////////
/**
 * @brief   Connection request
 *
 * @param   string  prefix
 * @param   bool    private
 *
 * @return  NullResponse
 */
struct ConnectRequest : public
        Request<constants::CallId::CONNECT, std::string, std::string, bool>
{
    static void write(IOBuffer&, const std::string&, bool);
private:
    static std::string mkSessionID();
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Create folder defined by list of properties
 *
 * @param   string          homedir
 * @param   uint32_t        cpid
 * @param   TaggedPropval[] propvals
 *
 * @return  Response<CreateFolderByPropertiesRequest::callId>
 */
struct CreateFolderByPropertiesRequest : public Request<constants::CallId::CREATE_FOLDER_BY_PROPERTIES,
        std::string, uint32_t, Collection<uint16_t, structures::TaggedPropval>>
{};

/**
 * @brief      Response specialization for CreateFolderByPropertiesRequest
 */
template<>
struct Response<CreateFolderByPropertiesRequest::callId>
{
    Response() = default;
    explicit Response(IOBuffer&);

    uint64_t folderId; ///< ID of the newly created folder
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Delete folder
 *
 * @param   string      homedir
 * @param   uint32_t    cpid
 * @param   uint64_t    folderId
 * @param   bool        hard
 *
 * @return  SuccessResponse
 */
struct DeleteFolderRequest : public Request<constants::CallId::DELETE_FOLDER,
        std::string, uint32_t, uint64_t, bool>
{};


/**
 * Response type override for delete folder request (-> SuccessResponse)
 */
template<>
struct response_map<DeleteFolderRequest::callId>
{using type = SuccessResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Get all store proptags request
 *
 * @param   string      homedir
 *
 * @return  Response<GetAllStorePropertiesRequest::callId>
 */
struct GetAllStorePropertiesRequest : public Request<constants::CallId::GET_STORE_ALL_PROPTAGS,
        std::string>
{};

/**
 * @brief      Response specialization for GetAllStorePropertiesRequest
 */
template<>
struct Response<GetAllStorePropertiesRequest::callId>
{
    Response() = default;
    explicit Response(IOBuffer&);

    std::vector<uint32_t> proptags; ///< List of prop tags contained in the store
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Get folder properties
 *
 * @param   string      homedir
 * @param   uint32_t    cpid
 * @param   uint64_t    folderId
 * @param   uint32_t[]  proptags
 *
 * @return PropvalResponse
 */
struct GetFolderPropertiesRequest : public Request<constants::CallId::GET_FOLDER_PROPERTIES,
        std::string, uint32_t, uint64_t, Collection<uint16_t, uint32_t>>
{};

/**
 * Response type override for get folder properties request (-> PropvalResponse)
 */
template<>
struct response_map<GetFolderPropertiesRequest::callId>
{using type = PropvalResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Get store properties request
 *
 * @param   string      homedir
 * @param   uint32_t    cpid
 * @param   uint32_t[]  proptags
 *
 * @return  PropvalResponse
 */
struct GetStorePropertiesRequest : public Request<constants::CallId::GET_STORE_PROPERTIES,
        std::string, uint32_t, Collection<uint16_t, uint32_t>>
{};

/**
 * Response type override for get store properties request (-> PropvalResponse)
 */
template<>
struct response_map<GetStorePropertiesRequest::callId>
{using type = PropvalResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Load data into a table
 *
 * Recursively loads all elements below `folderId` into a table.
 *
 * Use QueryTableRequest to retrieve the loaded data.
 *
 * Note that the table must be manually unloaded with UnloadTableRequest after
 * usage.
 *
 * @param   string      homedir
 * @param   uint64_t    folderId
 * @param   string      username
 * @param   uint8_t     tableFlags
 *
 * @return  LoadTableResponse
 */
struct LoadHierarchyTableRequest : public Request<constants::CallId::LOAD_HIERARCHY_TABLE,
        std::string, uint64_t, std::string, uint8_t, bool>
{static void write(IOBuffer&, const std::string&, const uint64_t&, const std::string&, const uint8_t&);};

/**
 * Response type override for load hierarchy table request (-> LoadTableResponse)
 */
template<>
struct response_map<LoadHierarchyTableRequest::callId>
{using type = LoadTableResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Load folder permission table
 *
 * Use QueryTableRequest to retrieve the loaded data.
 *
 * Note that the table must be manually unloaded with UnloadTableRequest after
 * usage.
 *
 * @param   string      homedir
 * @param   uint64_t    folderId
 * @param   uint8_t     tableFlags
 *
 * @return  LoadTableResponse
 */
struct LoadPermissionTableRequest : public Request<constants::CallId::LOAD_PERMISSION_TABLE,
        std::string, uint64_t, uint8_t>
{};

/**
 * Response type override for load hierarchy table request (-> LoadTableResponse)
 */
template<>
struct response_map<LoadPermissionTableRequest::callId>
{using type = LoadTableResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Retrieve data from previously loaded table
 *
 * @param   string      homedir
 * @param   string      username;
 * @param   uint32_t    cpid;
 * @param   uint32_t    tableId;
 * @param   uint32_t[]  proptags;
 * @param   uint32_t    startPos;
 * @param   uint32_t    rowNeeded;
 *
 * @return  Response<QueryTableRequest::callId>
 */
struct QueryTableRequest : public Request<constants::CallId::QUERY_TABLE,
        std::string, std::string, uint32_t, uint32_t, Collection<uint16_t, uint32_t>, uint32_t, uint32_t>
{};

/**
 * @brief      Response specialization for QueryTableRequest
 */
template<>
struct Response<QueryTableRequest::callId>
{
    Response() = default;
    explicit Response(IOBuffer&);

    std::vector<std::vector<structures::TaggedPropval> > entries; ///< Returned rows of entries
};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Delete proptags from store
 *
 * @param   string      homedir
 * @param   uint32_t[]  proptags
 *
 * @return
 */
struct RemoveStorePropertiesRequest: public Request<constants::CallId::REMOVE_STORE_PROPERTIES,
        std::string, Collection<uint16_t, uint32_t>>
{};


///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Set folder properties
 *
 * @param   string          homedir
 * @param   uint32_t        cpid
 * @param   uint64_t        folderId
 * @param   TaggedPropval[] propvals
 *
 * @return  ProblemsResponse
 */
struct SetFolderPropertiesRequest : public Request<constants::CallId::SET_FOLDER_PROPERTIES,
        std::string, uint32_t, uint64_t, Collection<uint16_t, structures::TaggedPropval>>
{};


/**
 * Response type override for set folder properties request (-> ProblemsResponse)
 */
template<>
struct response_map<SetFolderPropertiesRequest::callId>
{using type = ProblemsResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Update store properties
 *
 * @param   string          homedir
 * @param   uint32_t        cpid
 * @param   TaggedPropval[] propvals
 *
 * @return  ProblemsResponse
 */
struct SetStorePropertiesRequest : public Request<constants::CallId::SET_STORE_PROPERTIES,
        std::string, uint32_t, Collection<uint16_t, structures::TaggedPropval>>
{};


/**
 * Response type override for set store properties request (-> ProblemsResponse)
 */
template<>
struct response_map<SetStorePropertiesRequest::callId>
{using type = ProblemsResponse;};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Close store database
 *
 * @param   string  homedir
 *
 * @return  NullResponse
 */
struct UnloadStoreRequest : public Request<constants::CallId::UNLOAD_STORE, std::string>{};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Unload table
 *
 * @param   string      homedir
 * @param   uint32_t    tableId
 *
 * @return  NullResponse
 */
struct UnloadTableRequest : public Request<constants::CallId::UNLOAD_TABLE, std::string, uint32_t> {};

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief   Update folder permissions
 *
 * @param   string              homedir
 * @param   uint64_t            folderId
 * @param   bool                freebusy
 * @param   PermissionData[]    permissions
 *
 * @return  NullResponse
 */
struct UpdateFolderPermissionRequest : public Request<constants::CallId::UPDATE_FOLDER_PERMISSION,
        std::string, uint64_t, bool, Collection<uint16_t, structures::PermissionData>>
{};

}

}
