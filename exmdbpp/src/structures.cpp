/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020-2021 grammm GmbH
 */
#include <cstring>

#include "structures.h"
#include "constants.h"
#include "IOBufferImpl.h"
#include "util.h"

using namespace exmdbpp::constants;

namespace exmdbpp::structures
{
/**
 * @brief      Deserialize PropTag from buffer
 *
 * @param      buff  Buffer containing serialized PropTag
 */
TaggedPropval::TaggedPropval(IOBuffer& buff)
{
    tag = buff.pop<uint32_t>();
    type = tag == PropvalType::UNSPECIFIED? buff.pop<uint16_t>() : tag&0xFFFF;
    uint16_t svtype = (type&0x3000) == 0x3000? type & ~0x3000 : type;
    switch(svtype)
    {
    default:
        throw std::runtime_error("Deserialization of type "+std::to_string(type)+" is not supported.");
    case PropvalType::BYTE:
        buff >> value.u8; break;
    case PropvalType::SHORT:
        buff >> value.u16; break;
    case PropvalType::LONG:
    case PropvalType::ERROR:
        buff >> value.u32; break;
    case PropvalType::LONGLONG:
    case PropvalType::CURRENCY:
    case PropvalType::FILETIME:
        buff >> value.u64; break;
    case PropvalType::FLOAT:
        buff >> value.f; break;
    case PropvalType::DOUBLE:
    case PropvalType::FLOATINGTIME:
        buff >> value.d; break;
    case PropvalType::STRING:
    case PropvalType::WSTRING:
        const char* str = buff.pop<const char*>();
        size_t len = strlen(str);
        value.str = new char[len+1];
        strcpy(value.str, str); break;
    }
}

/**
 * @brief      Initialize tagged property value (8 bit unsigned)
 *
 * No type check is performed to ensure the tag type actually matches 8 bit unsigned.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, uint8_t val) : tag(tag), type(tag&0xFFFF)
{value.u8 = val;}

/**
 * @brief      Initialize tagged property value (16 bit unsigned)
 *
 * No type check is performed to ensure the tag type actually matches 16 bit unsigned.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, uint16_t val) : tag(tag), type(tag&0xFFFF)
{value.u16 = val;}

/**
 * @brief      Initialize tagged property value (32 bit unsigned)
 *
 * No type check is performed to ensure the tag type actually matches 32 bit unsigned.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, uint32_t val) : tag(tag), type(tag&0xFFFF)
{value.u32 = val;}

/**
 * @brief      Initialize tagged property value (64 bit unsigned)
 *
 * No type check is performed to ensure the tag type actually matches 64 bit unsigned.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, uint64_t val) : tag(tag), type(tag&0xFFFF)
{value.u64 = val;}

/**
 * @brief      Initialize tagged property value (32 bit floating point)
 *
 * No type check is performed to ensure the tag type actually matches 32 bit floating point.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, float val) : tag(tag), type(tag&0xFFFF)
{value.f = val;}

/**
 * @brief      Initialize tagged property value (64 bit floating point)
 *
 * No type check is performed to ensure the tag type actually matches 64 bit floating point.
 *
 * @param      tag        Tag identifier
 * @param      val        Tag value
 */
TaggedPropval::TaggedPropval(uint32_t tag, double val) : tag(tag), type(tag&0xFFFF)
{value.d = val;}

/**
 * @brief      Initialize tagged property value (C string)
 *
 * No type check is performed to ensure the tag type actually matches a string type.
 *
 * If copy is set to true, the data is copied to an internally managed buffer,
 * otherwise only the pointer to the data is stored.
 *
 * @param      tag   Tag identifier
 * @param      val   Tag value
 * @param      copy  Whether to copy data
 */
TaggedPropval::TaggedPropval(uint32_t tag, const char* val, bool copy) : tag(tag), type(tag&0xFFFF), owned(copy)
{
    if(copy)
        copyStr(val);
    else
        value.str = const_cast<char*>(val);
}

/**
 * @brief      Initialize tagged property value (binary)
 *
 * No type check is performed to ensure the tag type actually matches a binary type.
 *
 * Serialization expects the first 4 bytes of the data to contain a little endian
 * unsigned 32 bit integer with length information about the following data.
 *
 * If copy is set to true, the data is copied to an internally managed buffer,
 * otherwise only the pointer to the data is stored.
 *
 * @param      tag   Tag identifier
 * @param      val   Tag value
 * @param      copy  Whether to copy data
 * @param      len   Length of the buffer
 */
TaggedPropval::TaggedPropval(uint32_t tag, const void* val, bool copy, size_t len) : tag(tag), type(tag&0xFFFF), owned(copy)
{
    if(copy)
        copyData(val, len);
    else
        value.ptr = const_cast<void*>(val);
}

/**
 * @brief      Initialize tagged property value (Buffer)
 *
 * No type check is performed to ensure the tag type actually matches a binary type.
 *
 * Serialization expects the first 4 bytes of the data to contain a little endian
 * unsigned 32 bit integer with length information about the following data.
 *
 * If copy is set to true, the data is copied to an internally managed buffer,
 * otherwise only the pointer to the data is stored.
 *
 * @param      tag   Tag identifier
 * @param      val   Tag value
 * @param      copy  Whether to copy data
 */
TaggedPropval::TaggedPropval(uint32_t tag, const IOBuffer& val, bool copy) : tag(tag), type(tag&0xFFFF), owned(copy)
{
    if(copy)
        copyData(val.data(), val.size());
    else
        value.ptr = const_cast<void*>(reinterpret_cast<const void*>(val.data()));
}

/**
 * @brief      Initialize tagged property value (C++ string)
 *
 * No type check is performed to ensure the tag type actually matches a string type.
 *
 * If copy is set to true, the data is copied to an internally managed buffer,
 * otherwise only the pointer to the data is stored.
 *
 * @param      tag   Tag identifier
 * @param      val   Tag value
 * @param      copy  Whether to copy data
 */
TaggedPropval::TaggedPropval(uint32_t tag, const std::string& val, bool copy) : tag(tag), type(tag&0xFFFF), owned(copy)
{
    if(copy)
        copyData(val.c_str(), val.size()+1);
    else
        value.str = const_cast<char*>(val.c_str());
}

/**
 * @brief      Copy constructor
 *
 * @param      tp    TaggedPropval to copy
 */
TaggedPropval::TaggedPropval(const TaggedPropval& tp) : tag(tp.tag), type(tp.type)
{
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && tp.value.str != nullptr)
        copyStr(tp.value.str);
    else
        value = tp.value;
}

/**
 * @brief      Move constructor
 *
 * @param      tp    TaggedPropval to move data from
 */
TaggedPropval::TaggedPropval(TaggedPropval&& tp) : tag(tp.tag), type(tp.type), value(tp.value), owned(tp.owned)
{tp.value.ptr = nullptr;}

/**
 * @brief      Copy assignment operator
 *
 * @param      tp    TaggedPropval to copy
 *
 * @return     The result of the assignment
 */
TaggedPropval& TaggedPropval::operator=(const TaggedPropval& tp)
{
    free();
    tag = tp.tag;
    type = tp.type;
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && tp.value.str != nullptr)
        copyStr(tp.value.str);
    else
        value = tp.value;
    return *this;
}

/**
 * @brief      Move assignment operator
 *
 * @param      tp    TaggedPropval to move data from
 *
 * @return     The result of the assignment
 */
TaggedPropval& TaggedPropval::operator=(TaggedPropval&& tp)
{
    free();
    tag = tp.tag;
    type = tp.type;
    value = tp.value;
    owned = tp.owned;
    tp.value.ptr = nullptr;
    return *this;
}


/**
 * @brief      Destructor
 */
TaggedPropval::~TaggedPropval()
{
    free();
}

/**
 * @brief      Generate string representation of contained value
 *
 * Pretty prints contained value into a string.
 *
 * @return     String representation of value, according to type
 */
std::string TaggedPropval::printValue() const
{
    std::string content;
    uint16_t svtype = (type&0x3000) == 0x3000? type & ~0x3000 : type;
    time_t timestamp;
    switch(svtype)
    {
    case PropvalType::BYTE:
        content = std::to_string(int(value.u8)); break;
    case PropvalType::SHORT:
        content = std::to_string(int(value.u16)); break;
    case PropvalType::LONG:
    case PropvalType::ERROR:
        content = std::to_string(value.u32); break;
    case PropvalType::LONGLONG:
    case PropvalType::CURRENCY:
        content = std::to_string(value.u64); break;
    case PropvalType::FILETIME:
        timestamp = util::nxTime(value.u64);
        content = ctime(&timestamp);
        content.pop_back(); break;
    case PropvalType::FLOAT:
        content = std::to_string(value.f); break;
    case PropvalType::DOUBLE:
    case PropvalType::FLOATINGTIME:
        content = std::to_string(value.d); break;
    case PropvalType::STRING:
    case PropvalType::WSTRING:
        content = value.str; break;
    default:
        content = "[UNKNOWN]";
    }
    return content;
}

/**
 * @brief      Convert value to string
 *
 * Generates string represntation of the contained value.
 * In contrast to printValue(), the value is not interpreted but converted according to its type
 * (i.e. timestamps are not converted into human readable format, etc).
 *
 * @return     String representation of value, according to type
 */
std::string TaggedPropval::toString() const
{
    std::string content;
    uint16_t svtype = (type&0x3000) == 0x3000? type & ~0x3000 : type;
    switch(svtype)
    {
    case PropvalType::BYTE:
        content = std::to_string(int(value.u8)); break;
    case PropvalType::SHORT:
        content = std::to_string(int(value.u16)); break;
    case PropvalType::LONG:
    case PropvalType::ERROR:
        content = std::to_string(value.u32); break;
    case PropvalType::LONGLONG:
    case PropvalType::CURRENCY:
    case PropvalType::FILETIME:
        content = std::to_string(value.u64); break;
    case PropvalType::FLOAT:
        content = std::to_string(value.f); break;
    case PropvalType::DOUBLE:
    case PropvalType::FLOATINGTIME:
        content = std::to_string(value.d); break;
    case PropvalType::STRING:
    case PropvalType::WSTRING:
        content = value.str; break;
    default:
        content = "[UNKNOWN]";
    }
    return content;
}

/**
 * @brief      Copy string to internal buffer
 *
 * @param      str   String to copy
 */
void TaggedPropval::copyStr(const char* str)
{
    value.str = new char[strlen(str)+1];
    strcpy(value.str, str);
}

/**
 * @brief      Copy data to internal buffer
 *
 * @param      data  Data to copy
 * @param      len   Number of bytes
 */
void TaggedPropval::copyData(const void* data, size_t len)
{
    value.ptr = new char[len];
    memcpy(value.ptr, data, len);
}

/**
 * @brief      Clean up managed buffer
 */
void TaggedPropval::free()
{
    if((type == PropvalType::STRING || type == PropvalType::WSTRING || type == PropvalType::BINARY)
            && value.ptr != nullptr && owned)
        delete[] value.str;
}

/**
 * @brief      Create GUID from domain ID
 *
 * @param      domainId  Domain ID
 *
 * @return     Initialized GUID object
 */
GUID GUID::fromDomainId(uint32_t domainId)
{
    GUID guid;
    guid.timeLow = domainId;
    guid.timeMid = 0x0afb;
    guid.timeHighVersion = 0x7df6;
    guid.clockSeq[0] = 0x91;
    guid.clockSeq[1] = 0x92;
    guid.node[0] = 0x49;
    guid.node[1] = 0x88;
    guid.node[2] = 0x6a;
    guid.node[3] = 0xa7;
    guid.node[4] = 0x38;
    guid.node[5] = 0xce;
    return guid;
}


/**
 * @brief      Initialize XID with size information
 *
 * @param      size     Size of the XID object
 * @param      guid     GUID object
 * @param      localId  Local ID value (see util::valueToGc)
 */
SizedXID::SizedXID(uint8_t size, const GUID& guid, uint64_t localId) : guid(guid), localId(localId), size(size)
{}

/**
 * @brief      Write XID to buffer
 *
 * @param      buff     Buffer to write XID to
 */
void SizedXID::writeXID(IOBuffer& buff) const
{
    if(size < 17 || size > 24)
        throw std::runtime_error("Invalid XID size: "+std::to_string(size));
    uint64_t lId = htole64(localId);
    buff.push(guid);
    buff.push_raw(&lId, size-16);
}

const uint8_t PermissionData::ADD_ROW;
const uint8_t PermissionData::MODIFY_ROW;
const uint8_t PermissionData::REMOVE_ROW;


/**
 * @brief      Construct new PermissionData object
 *
 * @param      flags     Operation flags
 * @param      propvals  List of TaggedPropvals to modify
 */
PermissionData::PermissionData(uint8_t flags, const std::vector<TaggedPropval>& propvals) : flags(flags), propvals(propvals)
{}


/**
 * @brief      Load PropertyProblem from buffer
 *
 * @param      buff     Buffer to read data from
 */
PropertyProblem::PropertyProblem(IOBuffer& buff)
    : index(buff.pop<uint16_t>()), proptag(buff.pop<uint32_t>()), err(buff.pop<uint32_t>())
{}

}

namespace exmdbpp
{

using namespace structures;

/**
 * @brief      Serialize tagged propval to buffer
 *
 * @param      buff  Buffer to write data to
 * @param      pv    TaggedPropval to serialize
 */
template<>
void IOBuffer::Serialize<TaggedPropval>::push(IOBuffer& buff, const TaggedPropval& pv)
{
    uint16_t svtype = (pv.type&0x3000) == 0x3000? pv.type & ~0x3000 : pv.type;
    buff << pv.tag;
    if(pv.type == PropvalType::UNSPECIFIED)
        buff << pv.type;
    switch(svtype)
    {
    default:
        throw std::runtime_error("Serialization of type "+std::to_string(pv.type)+" is not supported.");
    case PropvalType::BYTE:
        buff << pv.value.u8; break;
    case PropvalType::SHORT:
        buff << pv.value.u16; break;
    case PropvalType::LONG:
    case PropvalType::ERROR:
        buff << pv.value.u32; break;
    case PropvalType::LONGLONG:
    case PropvalType::CURRENCY:
    case PropvalType::FILETIME:
        buff << pv.value.u64; break;
    case PropvalType::FLOAT:
        buff << pv.value.f; break;
    case PropvalType::DOUBLE:
    case PropvalType::FLOATINGTIME:
        buff << pv.value.d; break;
    case PropvalType::STRING:
    case PropvalType::WSTRING:
        buff << pv.value.str; break;
    case PropvalType::BINARY:
        uint32_t len;
        memcpy(&len, pv.value.ptr, sizeof(len));
        len = le32toh(len);
        buff.push_raw(pv.value.ptr, len+sizeof(uint32_t)); break;
    }
}

/**
 * @brief      Serialize GUID to buffer
 *
 * @param      buff  Buffer to write data to
 * @param      guid  GUID to serialize
 */
template<>
void IOBuffer::Serialize<GUID>::push(IOBuffer& buff, const GUID& guid)
{buff.push(guid.timeLow, guid.timeMid, guid.timeHighVersion, guid.clockSeq, guid.node);}

/**
 * @brief      Serialize XID with size information to buffer
 *
 * @param      buff  Buffer to write data to
 * @param      sXID  SizedXID to serialize
 */
template<>
void IOBuffer::Serialize<SizedXID>::push(IOBuffer& buff, const SizedXID& sXID)
{
    if(sXID.size < 17 || sXID.size > 24)
        throw std::runtime_error("Invalid XID size: "+std::to_string(sXID.size));
    buff.push(sXID.size);
    sXID.writeXID(buff);
}

/**
 * @brief      Serialize PermissionData to buffer
 *
 * @param      buff  Buffer to write data to
 */
template<>
void IOBuffer::Serialize<PermissionData>::push(IOBuffer& buff, const PermissionData& pd)
{
    buff.push(pd.flags, uint16_t(pd.propvals.size()));
    for(auto& propval : pd.propvals)
        buff.push(propval);
}

}
