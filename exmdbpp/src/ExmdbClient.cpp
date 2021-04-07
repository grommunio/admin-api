/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020-2021 grammm GmbH
 */
#include "ExmdbClient.h"

#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <unistd.h>

#include <stdexcept>

#include "constants.h"
#include "IOBufferOps.h"

namespace exmdbpp
{

using namespace requests;
using namespace constants;

/**
 * @brief      Constructor
 *
 * @param      message  Error message
 * @param      code     Exmdb response code
 */
ExmdbError::ExmdbError(const std::string& message, uint8_t code) : std::runtime_error(message+std::to_string(code)), code(code)
{}

///////////////////////////////////////////////////////////////////////////////////////////////////


static const addrinfo aiHint = {
    0, //ai_flags
    AF_UNSPEC, //ai_family
    SOCK_STREAM, //ai_socktype
    0, //ai_protocol
    0, nullptr, nullptr, nullptr
};

/**
 * @brief      Destructor
 *
 * Automatically closes the socket if it is still open.
 */
ExmdbClient::Connection::~Connection()
{close();}

/**
 * @brief      Close the socket
 *
 * Has no effect when the socket is already closed.
 */
void ExmdbClient::Connection::close()
{
    if(sock != -1)
        ::close(sock);
    sock = -1;
}

/**
 * @brief      Connect to server
 *
 * Establishes a TCP connection to the specified server.
 *
 * @param      host  Server address
 * @param      port  Server port or service
 *
 * @throws     std::runtime_error Connection could not be established
 */
void ExmdbClient::Connection::connect(const std::string& host, const std::string& port)
{
    if(sock != -1)
        close();
    addrinfo* addrs;
    int error;
    if((error = getaddrinfo(host.c_str(), port.c_str(), &aiHint, &addrs)))
        throw std::runtime_error("Could not resolve address: "+std::string(gai_strerror(error)));
    for(addrinfo* addr = addrs; addr != nullptr; addr = addr->ai_next)
    {
        if((sock = socket(addr->ai_family, addr->ai_socktype, addr->ai_protocol))  == -1)
            continue;
        if(::connect(sock, addr->ai_addr, addr->ai_addrlen) == 0)
            break;
        error = errno;
        ::close(sock);
        sock = -1;
    }
    freeaddrinfo(addrs);
    if(sock == -1)
        throw std::runtime_error("Connect failed: "+std::string(strerror(error)));
}

/**
 * @brief      Send request
 *
 * Sends data contained in the buffer to the server.
 *
 * The response code and length are inspected and the response (excluding status code and length)
 * is written back into the buffer.
 *
 * @param      buff  Buffer used for sending and receiving data
 */
void ExmdbClient::Connection::send(IOBuffer& buff)
{
    ssize_t bytes = ::send(sock, buff.data(), buff.size(), MSG_NOSIGNAL);
    if(bytes < 0)
        throw std::runtime_error("Send failed: "+std::string(strerror(errno)));
    buff.resize(5);
    bytes = recv(sock, buff.data(), 5, 0);
    if(bytes < 0)
        throw std::runtime_error("Receive failed: "+std::string(strerror(errno)));
    uint8_t status = buff.pop<uint8_t>();
    if(status != ResponseCode::SUCCESS)
        throw ExmdbError("Server returned non-zero response code ", status);
    if(bytes < 5)
        throw std::runtime_error("Connection closed unexpectedly");
    uint32_t length = buff.pop<uint32_t>();
    buff.reset();
    buff.resize(length);
    for(uint32_t offset = 0;offset < length;offset += bytes)
    {
        bytes = recv(sock, buff.data(), length, 0);
        if(bytes < 0)
            throw std::runtime_error("Message reception failed");
        if(bytes == 0)
            throw std::runtime_error("Connection closed unexpectedly");
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/**
 * @brief      Initialize client and connect to server
 *
 * @param      host       Server adress
 * @param      port       Server port
 * @param      prefix     Data area prefix (passed to ConnectRecquest)
 * @param      isPrivate  Whether to access private or public data (passed to ConnectRequest)
 */
ExmdbClient::ExmdbClient(const std::string& host, const std::string& port, const std::string& prefix, bool isPrivate)
{connect(host, port, prefix, isPrivate);}

/**
 * @brief      Connect to server
 *
 * @param      host       Server adress
 * @param      port       Server port
 * @param      prefix     Data area prefix (passed to ConnectRecquest)
 * @param      isPrivate  Whether to access private or public data (passed to ConnectRequest)
 */
void ExmdbClient::connect(const std::string& host, const std::string& port, const std::string& prefix, bool isPrivate)
{
    connection.connect(host, port);
    send(ConnectRequest(prefix, isPrivate));
}

}
