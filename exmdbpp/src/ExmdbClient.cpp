 #include "ExmdbClient.h"

#include <sys/types.h>
#include <sys/socket.h>
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
 * @brief      Initialize connection
 *
 * Creates a socket, but does not connect to any service yet.
 *
 * @throws     std::runtime_error Socket creation failed
 */
ExmdbClient::Connection::Connection()
{
    sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if(sock == -1)
        throw std::runtime_error("Socket initialization failed: "+std::string(strerror(errno)));
}

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
 * @param      port  Server port
 *
 * @throws     std::runtime_error Connection could not be established
 */
void ExmdbClient::Connection::connect(const std::string& host, uint16_t port)
{
    if(sock == -1)
        return;
    sockaddr_in server;
    server.sin_addr.s_addr = inet_addr(host.c_str());
    server.sin_family = AF_INET;
    server.sin_port = htons(port);
    if(::connect(sock, reinterpret_cast<sockaddr*>(&server), sizeof(server)))
        throw std::runtime_error("Connect failed: "+std::string(strerror(errno)));
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
        throw std::runtime_error("Call failed with response code "+std::to_string(int(status)));
    if(bytes < 5)
        throw std::runtime_error("Connection closed unexpectedly");
    uint32_t length = buff.pop<uint32_t>();
    if(status != ResponseCode::SUCCESS)
        throw std::runtime_error("Call failed with response code "+std::to_string(int(status)));
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
ExmdbClient::ExmdbClient(const std::string& host, uint16_t port, const std::string& prefix, bool isPrivate)
{connect(host, port, prefix, isPrivate);}

/**
 * @brief      Connect to server
 *
 * @param      host       Server adress
 * @param      port       Server port
 * @param      prefix     Data area prefix (passed to ConnectRecquest)
 * @param      isPrivate  Whether to access private or public data (passed to ConnectRequest)
 */
void ExmdbClient::connect(const std::string& host, uint16_t port, const std::string& prefix, bool isPrivate)
{
    connection.connect(host, port);
    send(ConnectRequest(prefix, isPrivate));
}



}
