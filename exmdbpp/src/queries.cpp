#include "queries.h"
#include "ExmdbClient.h"
#include "util.h"
#include "constants.h"

namespace exmdbpp::queries
{

/**
 * @brief      Retrieve public folder list
 *
 * Provides a higher level protocol implementation for retrieving
 * the public folders of a domain.
 *
 * @param      client   Client with active server connection
 * @param      homedir  Home directory path of the domain
 *
 * @return     Response of the QueryTableRequest
 */
Response<QueryTableRequest> getFolderList(ExmdbClient& client, const std::string& homedir)
{
    uint64_t folderId = util::makeEidEx(1, PublicFid::IPMSUBTREE);
    LoadHierarchyTableRequest lhtRequest(homedir, folderId, "", 0);
    auto lhtResponse = client.send(lhtRequest);
    std::vector<uint32_t> proptags = {PropTag::FOLDERID, PropTag::DISPLAYNAME, PropTag::COMMENT, PropTag::CREATIONTIME};
    QueryTableRequest qtRequest(homedir, "", 0, lhtResponse.tableId, proptags, 0, lhtResponse.rowCount);
    auto qtResponse = client.send(qtRequest);
    client.send(UnloadTableRequest(homedir, lhtResponse.tableId));client.send(UnloadTableRequest(homedir, lhtResponse.tableId));
    return qtResponse;
}

}
