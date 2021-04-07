#pragma once

#include <cstdint>
#include <string>
#include <array>
#include <vector>

namespace exmdbpp
{

class IOBuffer;

/**
 * @brief   MAPI structures
 */
namespace structures
{

/**
 * @brief      Tagged property value
 */
class TaggedPropval
{
public:


    TaggedPropval() = default;
    TaggedPropval(IOBuffer&);
    TaggedPropval(const TaggedPropval&);
    TaggedPropval(TaggedPropval&&);
    ~TaggedPropval();

    TaggedPropval(uint32_t, uint8_t);
    TaggedPropval(uint32_t, uint16_t);
    TaggedPropval(uint32_t, uint32_t);
    TaggedPropval(uint32_t, uint64_t);
    TaggedPropval(uint32_t, float);
    TaggedPropval(uint32_t, double);
    TaggedPropval(uint32_t, const char*, bool=true);
    TaggedPropval(uint32_t, const void*, bool=true, size_t=0);
    TaggedPropval(uint32_t, const IOBuffer&, bool=true);
    TaggedPropval(uint32_t, const std::string&, bool=true);


    TaggedPropval& operator=(const TaggedPropval&);
    TaggedPropval& operator=(TaggedPropval&&);

    std::string printValue() const;
    std::string toString() const;

    uint32_t tag = 0; ///< Tag identifier
    uint16_t type = 0; ///< Type of the tag (either derived from tag or explicitely specified if tag type is UNSPECIFIED)

    union Value
    {
        uint8_t u8;
        uint16_t u16;
        uint32_t u32;
        uint64_t u64;
        float f;
        double d;
        char* str;
        uint16_t* wstr;
        void* ptr;
    } value; ///< Data contained by the tag

    void serialize(IOBuffer&) const;

private:
    bool owned = true; ///< Whether the memory stored in pointer values is owned (automatically deallocated in destructor)

    void copyStr(const char*);
    void copyData(const void*, size_t);
    void free();
};

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      GUID class
 */
struct GUID
{
    uint32_t timeLow;
    uint16_t timeMid;
    uint16_t timeHighVersion;
    std::array<uint8_t, 2> clockSeq;
    std::array<uint8_t, 6> node;

    static GUID fromDomainId(uint32_t);

    void serialize(IOBuffer&) const;
};

/**
 * @brief      XID class
 */
struct XID
{
    XID(const GUID&, uint64_t);

    GUID guid;
    uint64_t localId;

    void serialize(IOBuffer&, uint8_t) const;
};

/**
 * @brief      XID with size information
 */
struct SizedXID
{
    SizedXID(uint8_t, const GUID&, uint64_t);

    uint8_t size;
    XID xid;

    void serialize(IOBuffer&) const;
};

/**
 * @brief      Permission data struct
 */
struct PermissionData
{
    PermissionData(uint8_t, const std::vector<TaggedPropval>&);

    uint8_t flags;
    std::vector<TaggedPropval> propvals;

    void serialize(IOBuffer&) const;

    static const uint8_t ADD_ROW = 0x01;
    static const uint8_t MODIFY_ROW = 0x02;
    static const uint8_t REMOVE_ROW = 0x04;
};

/**
 * @brief      List of problems that occured while setting store properties
 */
struct PropertyProblem
{
    PropertyProblem() = default;
    PropertyProblem(IOBuffer&);

    uint16_t index;
    uint32_t proptag;
    uint32_t err;
};

}

}
