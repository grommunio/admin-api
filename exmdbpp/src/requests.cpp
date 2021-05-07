/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020 grammm GmbH
 */
#include "requests.h"
#include "IOBufferImpl.h"
#include "constants.h"

#include <random>
#include <chrono>

using namespace exmdbpp::structures;
using namespace exmdbpp::constants;

namespace exmdbpp
{

/**
 * @brief      Serialize collection into buffer
 *
 * Includes the size as SizeType element before the actual data.
 * If the number of elements cannot be represented by SizeType, a
 * std::range_error is thrown.
 *
 * @param      buff   Buffer to insert into
 * @param      col    Collection to serialize
 *
 * @tparam     SizeType  Type to use for length serialization
 * @tparam     T         Element type
 */
template<typename SizeType, typename T>
void IOBuffer::Serialize<Collection<SizeType, T>>::push(IOBuffer& buff, const Collection<SizeType, T>& col)
{
    constexpr size_t maxSize = std::numeric_limits<SizeType>::max();
    if(col.size() > maxSize)
        throw std::range_error("Array size "+std::to_string(col.size())+
                               " is too large for SizeType (max "+ std::to_string(maxSize)+")");
    IOBuffer::Serialize<SizeType>::push(buff, SizeType(col.size()));
    for(auto const& v : col)
        IOBuffer::Serialize<typename Collection<SizeType, T>::value_type>::push(buff, v);
}

}


namespace exmdbpp::requests
{

/**
 * @brief      Deserialize load table response
 *
 * @param      buff  Buffer containing the data
 */
LoadTableResponse::LoadTableResponse(IOBuffer& buff)
{buff.pop(tableId, rowCount);}

/**
 * @brief      Deserialize problems response
 *
 * @param     buff      Buffer containing the response
 */
ProblemsResponse::ProblemsResponse(IOBuffer& buff)
{
    size_t count = buff.pop<uint16_t>();
    problems.reserve(count);
    for(size_t i = 0; i < count; ++i)
        problems.emplace_back(buff);
}

/**
 * @brief      Deserialize propval response
 *
 * @param      buff       Buffer containing the response
 */
PropvalResponse::PropvalResponse(IOBuffer& buff)
{
    uint16_t count = buff.pop<uint16_t>();
    propvals.reserve(count);
    for(uint16_t i = 0; i < count; ++i)
        propvals.emplace_back(buff);
}

/**
 * @brief      Deserialize response data
 *
 * @param      buff  Buffer containing the response
 */
SuccessResponse::SuccessResponse(IOBuffer& buff) : success(buff.pop<uint8_t>())
{}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Generic request serialization
 *
 * Provides serialization of call ID and parameters.
 *
 * Must be explicitely instantiated to be available to the linker.
 *
 * @param      buf   Buffer to wirte serialization to
 * @param      args  The arguments
 *
 * @tparam     ID    RPC call ID
 * @tparam     Args  RPC signature
 */
template<uint8_t ID, typename... Args>
void Request<ID, Args...>::Request:: write(IOBuffer& buf, const Args&... args)
{buf.push(ID, args...);}


static uint8_t SIDLEN = 15; ///< Length of the session ID
/// Available session ID characters
static const std::string sidchars("0123456789abcdefghjklmnopqrstvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
/// Rng used for session ID creation
static std::mt19937_64 rng(ulong(std::chrono::system_clock::now().time_since_epoch().count()));

/**
 * @brief      Initialize a connection request
 */
void ConnectRequest::ConnectRequest::write(IOBuffer& buf, const std::string& prefix, bool isPrivate)
{Request::write(buf, prefix, mkSessionID(), isPrivate);}

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

/**
 * @brief      LoadHierarchyTableRequest augmentation
 *
 * LoadHierarchyTable expects Restrictions, which are currently not implemented.
 *
 * @param      buff  Buffer containing the data
 */
void LoadHierarchyTableRequest::write(IOBuffer& buff, const std::string& homedir, const uint64_t& folderId,
                                      const std::string& username, const uint8_t& tableFlags)
{Request::write(buff, homedir, folderId, username, tableFlags, false);}

///////////////////////////////////////////////////////////////////////////////
//Response specializations

/**
 * @brief      Deserialize changenum allocation response
 *
 * @param      buff  Buffer containing the data
 */
Response<AllocateCnRequest::callId>::Response(IOBuffer& buff) : changeNum(buff.pop<uint64_t>())
{}

/**
 * @brief      Deserialize folder creation response
 *
 * @param      buff  Buffer containing the data
 */
Response<CreateFolderByPropertiesRequest::callId>::Response(IOBuffer& buff) : folderId(buff.pop<uint64_t>())
{}

/**
 * @brief      Deserialize query table response
 *
 * @param      buff  Buffer containing the data
 */
Response<QueryTableRequest::callId>::Response(IOBuffer& buff)
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
// Explicit template instantiations for requests

template struct Request<constants::CallId::ALLOCATE_CN, std::string>;
template struct Request<constants::CallId::CREATE_FOLDER_BY_PROPERTIES, std::string, uint32_t, Collection<uint16_t, structures::TaggedPropval>>;
template struct Request<constants::CallId::DELETE_FOLDER, std::string, uint32_t, uint64_t, bool>;
template struct Request<constants::CallId::GET_FOLDER_PROPERTIES, std::string, uint32_t, uint64_t, Collection<uint16_t, uint32_t>>;
template struct Request<constants::CallId::GET_STORE_PROPERTIES, std::string, uint32_t, Collection<uint16_t, uint32_t>>;
template struct Request<constants::CallId::LOAD_HIERARCHY_TABLE, std::string, uint64_t, std::string, uint8_t>;
template struct Request<constants::CallId::LOAD_PERMISSION_TABLE, std::string, uint64_t, uint8_t>;
template struct Request<constants::CallId::QUERY_TABLE, std::string, std::string, uint32_t, uint32_t, Collection<uint16_t, uint32_t>, uint32_t, uint32_t>;
template struct Request<constants::CallId::SET_FOLDER_PROPERTIES, std::string, uint32_t, uint64_t, Collection<uint16_t, structures::TaggedPropval>>;
template struct Request<constants::CallId::SET_STORE_PROPERTIES, std::string, uint32_t, Collection<uint16_t, structures::TaggedPropval>>;
template struct Request<constants::CallId::UNLOAD_STORE, std::string>;
template struct Request<constants::CallId::UNLOAD_TABLE, std::string, uint32_t>;
template struct Request<constants::CallId::UPDATE_FOLDER_PERMISSION, std::string, uint64_t, bool, Collection<uint16_t, structures::PermissionData>>;

}
