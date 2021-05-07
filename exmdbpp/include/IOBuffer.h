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
 * Implementation, including specializations for basic types, is provided in IOBufferImpl.h.
 */
class IOBuffer : public std::vector<uint8_t>
{
    /**
     * @brief      Helper struct providing serialization
     *
     * @tparam     T     Type to serialize/deserialize
     */
    template<typename T>
    struct Serialize
    {
        static void push(IOBuffer&, const T&);
        static void pop(IOBuffer&, T&);
    };

    template<typename T>
    friend struct Serialize;
public:
    using std::vector<uint8_t>::vector; ///< Use STL constructors

    void push_raw(const void*, size_t);
    template<typename T> void push(const T&);
    template<typename T, typename... Args> void push(const T&, const Args&...);

    const void* pop_raw(size_t);
    template<typename T> void pop(T&);
    template<typename T, typename... Args> void pop(T&, Args&...);
    template<typename T> T pop();

    void start();
    void finalize();

    void clear() noexcept;
    void reset() noexcept;

    size_t tell() const;
private:
      size_t rpos = 0; ///< Offset of the read cursor

      template<typename T> void push_T(const T&);
      template<typename T> void pop_T(T&);
};

///////////////////////////////////////////////////////////////////////////////

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
{
    uint32_t v = htole32(uint32_t(size() - 4));
    memcpy(data(), &v, sizeof(v));
}

}
