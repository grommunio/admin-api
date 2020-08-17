#include <cstring>

#include "structures.h"
#include "constants.h"
#include "IOBufferOps.h"
#include "util.h"

namespace exmdbpp
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
        throw std::runtime_error("Deserializaion of type "+std::to_string(type)+" is not supported.");
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
 * @brief      Copy constructor
 *
 * @param      tp    TaggedPropval to copy
 */
TaggedPropval::TaggedPropval(const TaggedPropval& tp) : tag(tp.tag), type(tp.type)
{
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && tp.value.str != nullptr)
    {
        value.str = new char[strlen(tp.value.str)+1];
        strcpy(value.str, tp.value.str);
    }
    else
        value = tp.value;
}

/**
 * @brief      Move constructor
 *
 * @param      tp    TaggedPropval to move data from
 */
TaggedPropval::TaggedPropval(TaggedPropval&& tp) : tag(tp.tag), type(tp.type), value(tp.value)
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
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && value.str != nullptr)
        delete[] value.str;
    tag = tp.tag;
    type = tp.type;
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && tp.value.str != nullptr)
    {
        value.str = new char[strlen(tp.value.str)+1];
        strcpy(value.str, tp.value.str);
    }
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
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && value.str != nullptr)
        delete[] value.str;
    tag = tp.tag;
    type = tp.type;
    value = tp.value;
    tp.value.ptr = nullptr;
    return *this;
}

/**
 * @brief      Destructor
 */
TaggedPropval::~TaggedPropval()
{
    if((type == PropvalType::STRING || type == PropvalType::WSTRING) && value.str != nullptr)
        delete[] value.str;
}

/**
 * @brief      Generate string representation of contained value
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

}
