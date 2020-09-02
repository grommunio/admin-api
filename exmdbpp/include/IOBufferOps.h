#pragma once

#include <array>

#include "IOBuffer.h"
#include <endian.h>

namespace exmdbpp
{

/**
 * @brief      Insert array of values into IOBuffer
 *
 * Inserts each value into the buffer using operator<< for correct
 * serialization.
 *
 * Only inserts the values without any length information or terminating
 * marker.
 *
 * @param      buff    Buffer to insert into
 * @param      values  Array of values to insert
 *
 * @tparam     T       Type of the values
 * @tparam     N       Number of elements
 *
 * @return     Reference to the buffer
 */
template<typename T, size_t N>
inline IOBuffer& operator<<(IOBuffer& buff, const std::array<T, N>& values)
{
    for(const T& value : values)
        buff << value;
    return buff;
}


/**
 * @brief      Insert uint8_t value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, uint8_t value)
{
    buff.push_back(value);
    return buff;
}

/**
 * @brief      Insert uint16_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, uint16_t value)
{
    buff.push(htole16(value));
    return buff;
}

/**
 * @brief      Insert uint32_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, uint32_t value)
{
    buff.push(htole32(value));
    return buff;
}

/**
 * @brief      Insert uint64_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, uint64_t value)
{
    buff.push(htole64(value));
    return buff;
}

/**
 * @brief      Insert float value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, float value)
{
    buff.push(value);
    return buff;
}

/**
 * @brief      Insert double value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, double value)
{
    buff.push(value);
    return buff;
}

/**
 * @brief      Insert C string into IOBuffer
 *
 * The terminating null character is automatically included.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, const char* value)
{
    for(const char* c = value; *c;++c)
        buff.push_back(static_cast<uint8_t>(*c));
    buff.push_back(0);
    return buff;
}

/**
 * @brief      Insert string into IOBuffer
 *
 * The terminating null character is automatically included.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, const std::string& value)
{
    buff.push(value.c_str(), value.length());
    buff.push_back(0);
    return buff;
}

/**
 * @brief      Insert ool value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator<<(IOBuffer& buff, bool value)
{
    buff.push_back(value);
    return buff;
}

/**
 * @brief      Extract uint8_t value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, uint8_t& value)
{
    value = *reinterpret_cast<const uint8_t*>(buff.pop(sizeof(value)));
    return buff;
}

/**
 * @brief      Extract uint16_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, uint16_t& value)
{
    value = le16toh(*reinterpret_cast<const uint16_t*>(buff.pop(sizeof(value))));
    return buff;
}

/**
 * @brief      Extract uint32_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, uint32_t& value)
{
    value = le32toh(*reinterpret_cast<const uint32_t*>(buff.pop(sizeof(value))));
    return buff;
}

/**
 * @brief      Extract uint64_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, uint64_t& value)
{
    value = le64toh(*reinterpret_cast<const uint64_t*>(buff.pop(sizeof(value))));
    return buff;
}

/**
 * @brief      Extract float value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, float& value)
{
    value = *reinterpret_cast<const float*>(buff.pop(sizeof(value)));
    return buff;
}

/**
 * @brief      Extract double value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, double& value)
{
    value = *reinterpret_cast<const double*>(buff.pop(sizeof(value)));
    return buff;
}

/**
 * @brief      Extract bool value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, bool& value)
{
    value = *reinterpret_cast<const uint8_t*>(buff.pop(sizeof(value)));
    return buff;
}

/**
 * @brief      Extract C string from IOBuffer
 *
 * No data is copied, the result should be processed/copied immediately to avoid invalidation by future reallocations.
 *
 * The read cursor is advanced until behind the terminating null character.
 * If the end of the buffer is reached before encountering a null character, a std::out_of_range exception is thrown.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, const char*& value)
{
    const char* temp = reinterpret_cast<const char*>(buff.data()+buff.tell());
    while(buff.pop<uint8_t>());
    value = temp;
    return buff;
}

/**
 * @brief      Extract string from IOBuffer
 *
 * Data gets copied into the string object, making this function safer than its C string counterpart.
 *
 * The read cursor is advanced until behind the terminating null character.
 * If the end of the buffer is reached before encountering a null character, a std::out_of_range exception is thrown.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 *
 * @return     Reference to the buffer
 */
inline IOBuffer& operator>>(IOBuffer& buff, std::string& value)
{
    const char* temp = reinterpret_cast<const char*>(buff.data()+buff.tell());
    while(buff.pop<uint8_t>());
    value = temp;
    return buff;
}

}
