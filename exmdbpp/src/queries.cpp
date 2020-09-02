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
    auto lhtResponse = client.send<LoadHierarchyTableRequest>(homedir, folderId, "", 0);
    std::vector<uint32_t> proptags = {PropTag::FOLDERID, PropTag::DISPLAYNAME, PropTag::COMMENT, PropTag::CREATIONTIME};
    auto qtResponse = client.send<QueryTableRequest>(homedir, "", 0, lhtResponse.tableId, proptags, 0, lhtResponse.rowCount);
    client.send<UnloadTableRequest>(homedir, lhtResponse.tableId);
    return qtResponse;
}

/**
 * @brief      Create a public folder
 *
 * @param      client      Client with active server connection
 * @param      homedir     Home directory path of the domain
 * @param      domainId    Domain ID
 * @param      folderName  Name of the new folder
 * @param      container   Folder container class
 * @param      comment     Comment to attach
 *
 * @return     Response returned by the server
 */
Response<CreateFolderByPropertiesRequest> createPublicFolder(ExmdbClient& client, const std::string& homedir, uint32_t domainId,
                                  const std::string& folderName, const std::string& container, const std::string& comment)
{
    auto acResponse = client.send<AllocateCnRequest>(homedir);
    std::vector<TaggedPropval> propvals;
    uint64_t now = util::ntTime();
    SizedXID xid(22, GUID::fromDomainId(domainId), util::valueToGc(acResponse.changeNum));
    IOBuffer tmpbuff;
    propvals.reserve(10);
    tmpbuff.reserve(128);
    propvals.emplace_back(PropTag::PARENTFOLDERID, util::makeEidEx(1, PublicFid::IPMSUBTREE));
    propvals.emplace_back(PropTag::FOLDERTYPE, FolderType::GENERIC);
    propvals.emplace_back(PropTag::DISPLAYNAME, folderName, false);
    propvals.emplace_back(PropTag::COMMENT, comment, false);
    propvals.emplace_back(PropTag::CREATIONTIME, now);
    propvals.emplace_back(PropTag::LASTMODIFICATIONTIME, now);
    propvals.emplace_back(PropTag::CHANGENUMBER, acResponse.changeNum);

    tmpbuff.start();
    xid.xid.serialize(tmpbuff, xid.size);
    tmpbuff.finalize();
    propvals.emplace_back(PropTag::CHANGEKEY, tmpbuff);

    tmpbuff.start();
    xid.serialize(tmpbuff);
    tmpbuff.finalize();
    propvals.emplace_back(PropTag::PREDECESSORCHANGELIST, tmpbuff, false);
    if(!container.empty())
        propvals.emplace_back(PropTag::CONTAINERCLASS, container);
    return client.send<CreateFolderByPropertiesRequest>(homedir, 0, propvals);
}

/**
 * @brief      Delete public folder
 *
 * @param      client    Client with active server connection
 * @param      homedir   Home directory path of the domain
 * @param      folderId  Id of the folder to delete
 *
 * @return     Response returned by the server
 */
Response<DeleteFolderRequest> deletePublicFolder(ExmdbClient& client, const std::string& homedir, uint64_t folderId)
{return client.send<DeleteFolderRequest>(homedir, 0, folderId, true);}

}
