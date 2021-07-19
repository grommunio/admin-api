/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020-2021 grommunio GmbH
 */
#include <cstring>
#include <type_traits>

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
    case PropvalType::WSTRING: {
        const char* str = buff.pop<const char*>();
        size_t len = strlen(str);
        value.str = new char[len+1];
        strcpy(value.str, str); break;
    }
    case PropvalType::BINARY: {
        uint32_t len = buff.pop<uint32_t>();
        if(len)
        {
            value.ptr = new uint8_t[len];
            memcpy(value.ptr, buff.pop_raw(len), len);
        }
    }
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
{free();}

static std::string hexData(const uint8_t* data, uint32_t len)
{
    static const char* digits = "0123456789ABCDEF";
    std::string str;
    str.reserve(len*2);
    for(const uint8_t* end = data+len; data < end; ++data)
    {
        str += digits[*data>>4];
        str += digits[*data&0xF];
    }
    return str;
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
    case PropvalType::BINARY: {
        content = *value.a32 > 20? "[DATA]" : hexData(value.a8+4, *value.a32); break;
    }
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
    case PropvalType::BINARY:
        content = "[DATA]"; break;
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

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

inline Restriction::RChain::RChain(std::vector<Restriction>&& ress) : elements(std::move(ress)) {}
inline Restriction::RNot::RNot(Restriction&& res) : res(new Restriction(std::move(res))) {}
inline Restriction::RContent::RContent(uint32_t fl, uint32_t pt, TaggedPropval&& tp) : fuzzyLevel(fl), proptag(pt != 0? pt : tp.tag), propval(std::move(tp)) {}
inline Restriction::RProp::RProp(Op op, uint32_t pt, TaggedPropval&& tp) : op(op), proptag(pt != 0? pt : tp.tag), propval(std::move(tp)) {}
inline Restriction::RPropComp::RPropComp(Op op, uint32_t pt1, uint32_t pt2) : op(op), proptag1(pt1), proptag2(pt2) {}
inline Restriction::RBitMask::RBitMask(bool all, uint32_t pt, uint32_t mask): all(all), proptag(pt), mask(mask) {}
inline Restriction::RSize::RSize(Op op, uint32_t pt, uint32_t size) : op(op), proptag(pt), size(size) {}
inline Restriction::RExist::RExist(uint32_t pt) : proptag(pt) {}
inline Restriction::RSubObj::RSubObj(uint32_t so, Restriction&& res) : subobject(so), res(new Restriction(std::move(res))) {}
inline Restriction::RComment::RComment(std::vector<TaggedPropval>&& tvs, Restriction&& res) : propvals(std::move(tvs)), res(res.res.index() == size_t(Type::iXNULL)? new Restriction(std::move(res)) : nullptr) {}
inline Restriction::RCount::RCount(uint32_t count, Restriction&& res) : count(count), subres(new Restriction(std::move(res))) {}

template<Restriction::Type I, typename... Args>
inline Restriction Restriction::create(Args&&... args)
{
    Restriction r;
    r.res.emplace<size_t(I)>(std::forward<Args>(args)...);
    return r;
}

/**
 * @brief       Create a new AND restriction chain
 *
 * Resulting restriction matches iff all sub restrictions match.
 *
 * @param       ress    Vector of sub restrictions
 *
 * @return      New AND restriction
 */
Restriction Restriction::AND(std::vector<Restriction>&& ress)
{return create<Type::AND>(std::move(ress));}

/**
 * @brief       Create a new OR restriction chain
 *
 * Resulting restriction matches iff at least on sub restriction matches.
 *
 * @param       ress    Vector of sub restrictions
 *
 * @return      New OR restriction
 */
Restriction Restriction::OR(std::vector<Restriction>&& ress)
{return create<Type::OR>(std::move(ress));}

/**
 * @brief       Create a new NOT restriction
 *
 * Resulting restriction matches iff sub restriction does not match
 *
 * @param       res     Sub restriction
 *
 * @return      New NOT restriction
 */
Restriction Restriction::NOT(Restriction&& res)
{return create<Type::NOT>(std::move(res));}

/**
 * @brief       Create a new CONTENT restriction
 *
 * Resulting restriction matches iff the string is contained in the property. Can only be applied to UNICODE proptags.
 *
 * `fuzzyLevel` can be one of FL_FULLSTRING, FL_SUBSTRING or FL_PREFIX,
 * optionally combined with one or more of FL_IGNORECASE, FL_IGNORENOSPACE or
 * FL_LOOSE.
 *
 * @param       fuzzyLevel  How precise the match must be
 * @param       proptag     Tag to match (or 0 to derive automatically from `propval`)
 * @param       propval     Propval to match against
 *
 * @return      New CONTENT restriction
 */
Restriction Restriction::CONTENT(uint32_t fuzzyLevel, uint32_t proptag, TaggedPropval&& propval)
{return create<Type::CONTENT>(fuzzyLevel, proptag, std::move(propval));}

/**
 * @brief       Create a new PROPERTY restriction
 *
 * Resulting restriction matches iff the property exists and matches (according
 * to the operator) the provided property.
 *
 * @param       op          Operator to apply
 * @param       proptag     Tag to match (or 0 to derive automatically from `propval`)
 * @param       propval     Propval to match against
 *
 * @return      New PROPERTY restriction
 */
Restriction Restriction::PROPERTY(Op op, uint32_t proptag, TaggedPropval&& propval)
{return create<Type::PROPERTY>(op, proptag, std::move(propval));}

/**
 * @brief       Create a new PROPCOMP restriction
 *
 * Resulting restriction matches iff the first tag matches (according to the
 * operator) the second tag.
 *
 * @param       op          Operator to apply
 * @param       proptag1    First operand
 * @param       proptag2    Second operand
 *
 * @return      New PROPCOMP restriction
 */
Restriction Restriction::PROPCOMP(Op op, uint32_t proptag1, uint32_t proptag2)
{return create<Type::PROPCOMP>(op, proptag1, proptag2);}

/**
 * @brief       Create a new BITMASK restriction
 *
 * Resulting restriction matches iff the bitmask overlaps with at least 1
 * (all = true) or no (all = false) bits of the target property.
 *
 * Can only be applied to LONG properties.
 *
 * @param       all         Whether the bitmask must match
 * @param       proptag     Tag to match
 * @param       mask        Bitmask to apply
 *
 * @return      New CONTENT restriction
 */
Restriction Restriction::BITMASK(bool all, uint32_t proptag, uint32_t mask)
{return create<Type::BITMASK>(all, proptag, mask);}

/**
 * @brief       Create a new SIZE restriction
 *
 * Resulting restriction matches iff the size of the proptag matches (according
 * to the operator) the specified size
 *
 * @param       op          Operator to apply
 * @param       proptag     Tag to match
 * @param       size        Memory size of tag value in bytes
 *
 * @return      New SIZE restriction
 */
Restriction Restriction::SIZE(Op op, uint32_t proptag, uint32_t size)
{return create<Type::SIZE>(op, proptag, size);}

/**
 * @brief       Create a new EXIST restriction
 *
 * Resulting restriction matches iff the proptag exists.
 *
 * @param       proptag     Tag to check
 *
 * @return      New EXIST restriction
 */
Restriction Restriction::EXIST(uint32_t proptag)
{return create<Type::EXIST>(proptag);}

/**
 * @brief       Create a new SUBOBJECT restriction
 *
 * Apply restriction to a specifig subobject. Possible subobjects are
 * `MESSAGERECIPIENTS` and `MESSAGEATTACHMENTS` properties.
 *
 * @param       res         Restriction to apply
 *
 * @return      New SUBOBJECT restriction
 */
Restriction Restriction::SUBOBJECT(uint32_t subobject, Restriction&& res)
{return create<Type::SUBRES>(subobject, std::move(res));}

/**
 * @brief       Create a new COMMENT restriction
 *
 * Restriction with arbitrary (unused) metadata.
 *
 * Matches iff the sub-restriction matches.
 *
 * @param       propvals    Properties acting as comments
 * @param       res         Restriction to apply
 *
 * @return      New COMMENT restriction
 */
Restriction Restriction::COMMENT(std::vector<TaggedPropval>&& propvals, Restriction&& res)
{return create<Type::COMMENT>(std::move(propvals), std::move(res));}

/**
 * @brief       Create a new COUNT restriction
 *
 * Resulting restriction matches iff sub-restriction matches, but only at most
 * `count` times.
 *
 * @param       count       Maximum number of matches
 * @param       subres      Sub-restriction to count
 *
 * @return      New SIZE restriction
 */
Restriction Restriction::COUNT(uint32_t count, Restriction&& subres)
{return create<Type::COUNT>(count, std::move(subres));}

/**
 * @brief       Create a new NULL restriction
 *
 * The NULL restriction is only a virtual construct and is not serialized and
 * sent to the server.
 *
 * @return      New NULL restriction
 */
Restriction Restriction::XNULL()
{return Restriction();}

/**
 * @brief       Serialize Restriction into IOBuffer
 *
 * @param       buff    Buffer to write serialized data to
 */
void Restriction::serialize(IOBuffer& buff) const
{
    Type type = Type(res.index());
    if(type == Type::iXNULL)
        return;
    buff.push(uint8_t(type));
    switch(type)
    {
    case Type::AND:
    case Type::OR: {
        const std::vector<Restriction>* ress = type == Type::AND? &std::get<size_t(Type::AND)>(res).elements : &std::get<size_t(Type::OR)>(res).elements;
        if(ress->size() > 2ull<<32)
            throw std::runtime_error("Too many sub-restrictions ("+std::to_string(ress->size())+")");
        buff.push(uint32_t(ress->size()));
        for(const Restriction& r : *ress)
            buff.push(r);
        return;
    }
    case Type::NOT:
        return buff.push(*std::get<size_t(Type::NOT)>(res).res);
    case Type::CONTENT: {
        const RContent& r = std::get<size_t(Type::CONTENT)>(res);
        return buff.push(r.fuzzyLevel, r.proptag, r.propval);
    }
    case Type::PROPERTY: {
        const RProp& r = std::get<size_t(Type::PROPERTY)>(res);
        return buff.push(uint8_t(r.op), r.proptag, r.propval);
    }
    case Type::PROPCOMP: {
        const RPropComp& r = std::get<size_t(Type::PROPCOMP)>(res);
        return buff.push(uint8_t(r.op), r.proptag1, r.proptag2);
    }
    case Type::BITMASK: {
        const RBitMask& r = std::get<size_t(Type::BITMASK)>(res);
        return buff.push(uint8_t(!r.all), r.proptag, r.mask);
    }
    case Type::SIZE: {
        const RSize& r = std::get<size_t(Type::SIZE)>(res);
        return buff.push(uint8_t(r.op), r.proptag, r.size);
    }
    case Type::EXIST: {
        const RExist& r = std::get<size_t(Type::EXIST)>(res);
        return buff.push(r.proptag);
    }
    case Type::SUBRES: {
        const RSubObj& r = std::get<size_t(Type::SUBRES)>(res);
        return buff.push(r.subobject, *r.res);
    }
    case Type::COMMENT: {
        const RComment& r = std::get<size_t(Type::COMMENT)>(res);
        if(r.propvals.size() == 0 || r.propvals.size() > 255)
            throw std::runtime_error("Invalid COMMENT restriction propval count "+std::to_string(r.propvals.size()));
        buff.push(uint8_t(r.propvals.size()));
        for(const TaggedPropval& tp : r.propvals)
            buff.push(tp);
        return r.res? buff.push(uint8_t(1), *r.res) : buff.push(uint8_t(0));
    }
    case Type::COUNT: {
        const RCount& r = std::get<size_t(Type::COUNT)>(res);
        return buff.push(r.count, *r.subres);
    }
    default:
        throw std::runtime_error("Invalid restriction type "+std::to_string(uint8_t(type)));
    }
}

/**
 * @brief       Check whether the restriction is non-empty
 */
Restriction::operator bool() const
{return res.index() != size_t(Type::iXNULL);}


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

template<>
void IOBuffer::Serialize<Restriction>::push(IOBuffer& buff, const Restriction& res)
{res.serialize(buff);}

}
