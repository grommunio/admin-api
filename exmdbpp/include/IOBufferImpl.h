#pragma once

#include <array>

#include "IOBuffer.h"
#include <endian.h>

namespace exmdbpp
{

/**
 * @brief      Serialize specialization for STL arrays
 *
 * @tparam     T    Element type
 * @tparam     N    Array length
 */
template<typename T, size_t N>
struct IOBuffer::Serialize<std::array<T, N>>
{static void push(IOBuffer&, const std::array<T, N>&);};


/**
 * @brief      Push data into the buffer
 *
 * Data is always appended at the end of the buffer.
 *
 * @param      data    Data to insert
 * @param      length  Number of bytes to append
 */
inline void IOBuffer::push_raw(const void* data, size_t length)
{insert(end(), reinterpret_cast<const uint8_t*>(data), reinterpret_cast<const uint8_t*>(data)+length);}

/**
 * @brief      Push data element without conversion
 *
 * @param      value  Value to push
 *
 * @tparam     T      Type of the element
 */
template<typename T>
inline void IOBuffer::push_T(const T& value)
{push_raw(&value, sizeof(value));}

/**
 * @brief      Push data into the buffer
 *
 * Data is serialized using IOBuffer::Serialize<T>::push.
 *
 * @param      value  Value to insert
 *
 * @tparam     T      Type of the value
 */
template<typename T>
inline void IOBuffer::push(const T& value)
{Serialize<T>::push(*this, value);}

/**
 * @brief      Variadic overload for push function
 *
 * @param      value  First value
 * @param      args   Further arguments
 *
 * @tparam     T      Type of the element
 * @tparam     Args   Further types
 */
template<typename T, typename... Args>
inline void IOBuffer::push(const T& value, const Args&... args)
{
    push(value);
    push(args...);
}

/**
 * @brief      Pop value from buffer without conversion
 *
 * @param      val   Destination object
 *
 * @tparam     T     Type of data to read
 */
template<typename T>
inline void IOBuffer::pop_T(T& val)
{
    memcpy(&val, pop_raw(sizeof(T)), sizeof(T));
}

/**
 * @brief      Return data of given length and advance read cursor
 *
 * If less than length bytes are available, a std::out_of_range exception is thrown.
 *
 * No data is copied by this call. Instead, a pointer to the internal buffer is returned.
 * The data should be copied / processed immediately as future reallocations will invalidate the pointer.
 *
 * @throw      std::out_of_range length is larger than the amount of available bytes
 *
 * @param      length  Number of bytes to read
 *
 * @return     Pointer to data
 */
inline const void* IOBuffer::pop_raw(size_t length)
{
    if(rpos+length > size())
        throw std::out_of_range("Read past the end of buffer. ("+std::to_string(length)+" bytes requested, "+
                                std::to_string(size()-rpos)+" bytes available)");
    rpos += length;
    return data()+rpos-length;
}

/**
 * @brief      Pop data from buffer
 *
 * Data is deserialized using IOBuffer::Serialize<T>::pop.
 *
 * @param      value  Destination object
 *
 * @tparam     T      Type of data to read
 */
template<typename T>
inline void IOBuffer::pop(T& value)
{Serialize<T>::pop(*this, value);}

/**
 * @brief      Variadic overload for pop function
 *
 * @param      value  First value
 * @param      args   Further arguments
 *
 * @tparam     T      Type of the element
 * @tparam     Args   Further types
 */
template<typename T, typename... Args>
inline void IOBuffer::pop(T& value, Args&... args)
{
    pop(value);
    pop(args...);
}

/**
 * @brief      Pop data from buffer
 *
 * Creates a local temporary, reads data into it and returns it.
 *
 * @tparam     T     Type of data to read
 *
 * @return     Read object
 */
template<typename T>
inline T IOBuffer::pop()
{
    T temp;
    pop(temp);
    return temp;
}

/**
 * @brief      Reset read pointer to beginning of the buffer.
 */
inline void IOBuffer::reset() noexcept
{rpos=0;}

/**
 * @brief      Return current position of the read cursor
 *
 * @return     Offset of the read cursor
 */
inline size_t IOBuffer::tell() const
{return rpos;}

///////////////////////////////////////////////////////////////////////////////

/**
 * @brief      IOBuffer insertion operator overload
 *
 * Convenience overload calling IOBuffer::push<T>(value).
 *
 * @param      buf    Buffer to insert data to
 * @param      value  Value to insert
 *
 * @tparam     T      Type of data to insert
 *
 * @return     Reference to the buffer
 */
template<typename T>
inline IOBuffer& operator<<(IOBuffer& buf, const T& value)
{
    buf.push(value);
    return buf;
}

/**
 * @brief      IOBuffer extraction operator overload
 *
 * @param      buf    Buffer to extract data from
 * @param      value  Value to extract
 *
 * @tparam     T      Type of data to extract
 *
 * @return     Reference to the buffer
 */
template<typename T>
inline IOBuffer& operator>>(IOBuffer& buf, T& value)
{
    buf.pop(value);
    return buf;
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Serialize element into buffer
 *
 * The base template does not provide any functionality and relies on
 * specialization to prevent undefined behavior due to unexpected overload
 * resolution.
 *
 * If no matching specialization is provided, an error is issued during compile
 * time.
 */
template<typename T>
inline void IOBuffer::Serialize<T>::push(IOBuffer&, const T&)
{static_assert(sizeof(T) != sizeof(T), "Serialization of this type is not implemented");}

/**
 * @brief      Insert uint8_t value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<uint8_t>::push(IOBuffer& buff, const uint8_t& value)
{buff.push_back(value);}

/**
 * @brief      Insert uint16_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<uint16_t>::push(IOBuffer& buff, const uint16_t& value)
{buff.push_T(htole16(value));}

/**
 * @brief      Insert uint32_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<uint32_t>::push(IOBuffer& buff, const uint32_t& value)
{buff.push_T(htole32(value));}

/**
 * @brief      Insert uint64_t value into IOBuffer
 *
 * The value is automatically converted to little endian byte order.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<uint64_t>::push(IOBuffer& buff, const uint64_t& value)
{buff.push_T(htole64(value));}

/**
 * @brief      Insert float value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<float>::push(IOBuffer& buff, const float& value)
{buff.push_T(value);}

/**
 * @brief      Insert double value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<double>::push(IOBuffer& buff, const double& value)
{buff.push_T(value);}

/**
 * @brief      Insert C string into IOBuffer
 *
 * The terminating null character is automatically included.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<const char*>::push(IOBuffer& buff, const char* const& value)
{buff.push_raw(value, strlen(value)+1);}

/**
 * @brief      Insert C string into IOBuffer
 *
 * The terminating null character is automatically included.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<char*>::push(IOBuffer& buff, char* const& value)
{buff.push(static_cast<const char*>(value));}

/**
 * @brief      Insert string into IOBuffer
 *
 * The terminating null character is automatically included.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<std::string>::push(IOBuffer& buff, const std::string& value)
{
    buff.push_raw(value.data(), value.length());
    buff.push_back(0);
}

/**
 * @brief      Insert bool value into IOBuffer
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<>
inline void IOBuffer::Serialize<bool>::push(IOBuffer& buff, const bool& value)
{buff.push_back(value);}

/**
 * @brief      Insert array of values into buffer
 *
 * Calls push<T> for each element of of `values`.
 * Does NOT write the number of elements to the buffer.
 *
 * @param      buff   Buffer to insert into
 * @param      value  Value to insert
 */
template<typename T, size_t N>
inline void IOBuffer::Serialize<std::array<T, N>>::push(IOBuffer& buff, const std::array<T, N>& values)
{
    for(const T& value : values)
        buff.push(value);
}
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Deserialize element from buffer
 *
 * The base template does not provide any functionality and relies on
 * specialization to prevent undefined behavior due to unexpected overload
 * resolution.
 *
 * If no matching specialization is provided, an error is issued during compile
 * time.
 */
template<typename T>
inline void IOBuffer::Serialize<T>::pop(IOBuffer&, T&)
{static_assert(sizeof(T) != sizeof(T), "Deserialization of this type is not implemented");}

/**
 * @brief      Extract uint8_t value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<uint8_t>::pop(IOBuffer& buff, uint8_t& value)
{value = *reinterpret_cast<const uint8_t*>(buff.pop_raw(sizeof(value)));}

/**
 * @brief      Extract uint16_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<uint16_t>::pop(IOBuffer& buff, uint16_t& value)
{
    buff.pop_T(value);
    value = le16toh(value);
}

/**
 * @brief      Extract uint32_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<uint32_t>::pop(IOBuffer& buff, uint32_t& value)
{
    buff.pop_T(value);
    value = le32toh(value);
}

/**
 * @brief      Extract uint64_t value from IOBuffer
 *
 * The data is automatically converted from little endian to host byte order.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<uint64_t>::pop(IOBuffer& buff, uint64_t& value)
{
    buff.pop_T(value);
    value = le64toh(value);
}

/**
 * @brief      Extract float value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<float>::pop(IOBuffer& buff, float& value)
{buff.pop_T(value);}

/**
 * @brief      Extract double value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<double>::pop(IOBuffer& buff, double& value)
{buff.pop_T(value);}

/**
 * @brief      Extract bool value from IOBuffer
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<bool>::pop(IOBuffer& buff, bool& value)
{value = *reinterpret_cast<const uint8_t*>(buff.pop_raw(sizeof(bool)));}

/**
 * @brief      Extract C string from IOBuffer
 *
 * No data is copied, the result should be processed/copied immediately to avoid invalidation by future reallocations.
 *
 * The read cursor is advanced behind the terminating null character.
 * If the end of the buffer is reached before encountering a null character, a std::out_of_range exception is thrown
 * and value remains unchanged.
 *
 * @param      buff   Buffer to extract from
 * @param      value  Value to extract into
 */
template<>
inline void IOBuffer::Serialize<const char*>::pop(IOBuffer& buff, const char*& value)
{
    const char* temp = reinterpret_cast<const char*>(buff.data()+buff.tell());
    while(*reinterpret_cast<const char*>(buff.pop_raw(1)));
    value = temp;
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
 */
template<>
inline void IOBuffer::Serialize<std::string>::pop(IOBuffer& buff, std::string& value)
{
    const char* temp = reinterpret_cast<const char*>(buff.data()+buff.tell());
    while(*reinterpret_cast<const char*>(buff.pop_raw(1)));
    value = temp;
}

}
