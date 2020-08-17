#pragma once

#include <vector>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <cstring>
#include <endian.h>

namespace exmdbpp
{
/**
 * @brief      I/O buffer class
 *
 * Can be used for serialization and deserialization of values and structures.
 *
 * Operator overloads for the << (write) and >> (read) operators supporting basic types are implemented in IOBufferOps.h.
 */
class IOBuffer : public std::vector<uint8_t>
{
public:
    using std::vector<uint8_t>::vector;

    void push(const void*, size_t);
    template<typename T> void push(const T&);
      const void* pop(size_t);
    template<typename T>
      T pop();

    void start();
    void finalize();

    void clear() noexcept;
    void reset() noexcept;

    size_t tell() const;
private:
      size_t rpos = 0; ///< Offset of the read cursor

};

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Push data into the buffer
 *
 * Data is always appended at the end of the buffer.
 *
 * @param      data    Data to insert
 * @param      length  Number of bytes to append
 */
inline void IOBuffer::push(const void* data, size_t length)
{insert(end(), reinterpret_cast<const uint8_t*>(data), reinterpret_cast<const uint8_t*>(data)+length);}


/**
 * @brief      Push data into the buffer
 *
 * Templated shortcut for push(const void*, size_t).
 * Directly inserts data into the buffer, without using operator<< to encode the object.
 *
 * @param      value  Value to insert
 *
 * @tparam     T      Type of the value
 */
template<typename T>
inline void IOBuffer::push(const T& value)
{push(&value, sizeof(value));}

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
inline const void* IOBuffer::pop(size_t length)
{
    if(rpos+length > size())
        throw std::out_of_range("Read past the end of buffer. ("+std::to_string(length)+" bytes requested, "+
                                std::to_string(size()-rpos)+" bytes available)");
    rpos += length;
    return data()+rpos-length;
}

/**
 * @brief      Clear the buffer
 *
 * Sets the size to zero and resets the read cursor to beginning.
 */
inline void IOBuffer::clear() noexcept
{
    std::vector<uint8_t>::clear();
    rpos = 0;
}

/**
 * @brief      Reset read pointer to beginning of the buffer.
 */
inline void IOBuffer::reset() noexcept
{rpos=0;}

/**
 * @brief      Start message serialization
 *
 * Resizes the buffer to 4 bytes, which are used to encode the total message length.
 */
inline void IOBuffer::start()
{resize(sizeof(uint32_t));}

/**
 * @brief      Stop message recording
 *
 * Writes the message length to the first four bytes of the buffer.
 */
inline void IOBuffer::finalize()
{*reinterpret_cast<uint32_t*>(data()) = htole32(uint32_t(size()-4));}

/**
 * @brief      Extract object from buffer
 *
 * Implicitely calls operator>> to support user defined pop implementations.
 *
 * @tparam     T     Type of object to extract
 *
 * @return     Deserialized object
 */
template<typename T>
T IOBuffer::pop()
{
    T temp;
    *this >> temp;
    return temp;
}

/**
 * @brief      Return current position of the read cursor
 *
 * @return     Offset of the read cursor
 */
inline size_t IOBuffer::tell() const
{return rpos;}

}
