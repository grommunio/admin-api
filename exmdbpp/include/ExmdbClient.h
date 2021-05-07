#pragma once

#include <string>
#include <vector>
#include <functional>
#include <exception>

#include "IOBuffer.h"
#include "requests.h"

/**
 * @brief Root namespace for the exmdbpp library
 */
namespace exmdbpp
{

/**
 * @brief   Exception thrown when exmdb server returns an error code
 */
class ExmdbError : public std::runtime_error
{
public:
    ExmdbError(const std::string&, uint8_t);

    const uint8_t code; ///< Response code returned by the server
};

/**
 * @brief   Client managing communication with the exmdb server
 */
class ExmdbClient
{
    class Connection
    {
    public:
        Connection() = default;
        ~Connection();

        void connect(const std::string&, const std::string&);
        void close();
        void send(IOBuffer&);

    private:
        int sock = -1; ///< TCP socket to send and receive data
    };

public:
    ExmdbClient() = default;
    ExmdbClient(const std::string&, const std::string&, const std::string&, bool);

    void connect(const std::string&, const std::string&, const std::string&, bool);

    template<class Request, typename... Args>
    requests::Response_t<Request> send(const Args&...);
private:
    Connection connection; ///< Connection used to send and receive data
    IOBuffer buffer; ///< Buffer managing data to send / received data
};

/**
 * @brief      Send request and parse response
 * *
 * See documentation of the specific Request for a description of the
 * parameters.
 *
 * @param      args     Values to serialize
 *
 * @tparam     Request  Type of the request
 * @tparam     Args     Request arguments
 *
 * @return     Parsed response object
 */
template<class Request, typename... Args>
inline requests::Response_t<Request> ExmdbClient::send(const Args&... args)
{
    buffer.clear();
    buffer.start();
    Request::write(buffer, args...);
    buffer.finalize();
    connection.send(buffer);
    return requests::Response_t<Request>(buffer);
}


}

