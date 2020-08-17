#pragma once

#include <cstdint>
#include <string>

namespace exmdbpp
{

class IOBuffer;

/**
 * @brief      Tagged property value
 */
struct TaggedPropval
{
    TaggedPropval() = default;
    TaggedPropval(IOBuffer&);
    TaggedPropval(const TaggedPropval&);
    TaggedPropval(TaggedPropval&&);
    ~TaggedPropval();

    TaggedPropval& operator=(const TaggedPropval&);
    TaggedPropval& operator=(TaggedPropval&&);

    std::string printValue() const;

    uint32_t tag; ///< Tag identifier
    uint16_t type; ///< Type of the tag (either derived from tag or explicitely specified if tag type is UNSPECIFIED)

    union
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
};

}
