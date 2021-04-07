/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020 grammm GmbH
 */
#include "queries.h"
#include "util.h"
#include "constants.h"

using namespace exmdbpp::constants;
using namespace exmdbpp::requests;
using namespace exmdbpp::structures;

namespace exmdbpp::queries
{

const std::vector<uint32_t> ExmdbQueries::defaultFolderProps =
{PropTag::FOLDERID, PropTag::DISPLAYNAME, PropTag::COMMENT, PropTag::CREATIONTIME, PropTag::CONTAINERCLASS};

/**
 * @brief      Interpret query table response as folder list
 *
 * @param      response  Response to convert
 */
FolderListResponse::FolderListResponse(const Response<QueryTableRequest>& response)
{
    folders.reserve(response.entries.size());
    for(auto& entry : response.entries)
    {
        Folder folder;
        for(const TaggedPropval& tp : entry)
        {
            switch(tp.tag)
            {
            case PropTag::FOLDERID:
                folder.folderId = tp.value.u64; break;
            case PropTag::DISPLAYNAME:
                folder.displayName = tp.value.str; break;
            case PropTag::COMMENT:
                folder.comment = tp.value.str; break;
            case PropTag::CREATIONTIME:
                folder.creationTime = tp.value.u64; break;
            case PropTag::CONTAINERCLASS:
                folder.container = tp.value.str; break;
            }
        }
        folders.emplace_back(std::move(folder));
    }
}

/**
 * @brief      Interpret query table response as folder owner list
 *
 * @param      response  Response to convert
 */
FolderOwnerListResponse::FolderOwnerListResponse(const Response<QueryTableRequest>& response)
{
    owners.reserve(response.entries.size());
    for(auto& entry : response.entries)
    {
        Owner owner;
        for(const TaggedPropval& tp : entry)
        {
            switch(tp.tag)
            {
            case PropTag::MEMBERID:
                owner.memberId = tp.value.u64; break;
            case PropTag::MEMBERNAME:
                owner.memberName = tp.value.str; break;
            case PropTag::MEMBERRIGHTS:
                owner.memberRights= tp.value.u32; break;
            }
        }
        owners.emplace_back(std::move(owner));
    }
}

/**
 * @brief      Retrieve public folder list
 *
 * Provides a higher level protocol implementation for retrieving
 * the public folders of a domain.
 *
 * @param      homedir  Home directory path of the domain
 * @param      proptags Tags to return
 *
 * @return     Response of the QueryTableRequest. Can be converted to FolderListResponse for easier access.
 */
Response<QueryTableRequest> ExmdbQueries::getFolderList(const std::string& homedir, const std::vector<uint32_t>& proptags)
{
    uint64_t folderId = util::makeEidEx(1, PublicFid::IPMSUBTREE);
    auto lhtResponse = send<LoadHierarchyTableRequest>(homedir, folderId, "", 0);
    auto qtResponse = send<QueryTableRequest>(homedir, "", 0, lhtResponse.tableId, proptags, 0, lhtResponse.rowCount);
    send<UnloadTableRequest>(homedir, lhtResponse.tableId);
    return qtResponse;
}

/**
 * @brief      Create a public folder
 *
 * @param      homedir     Home directory path of the domain
 * @param      domainId    Domain ID
 * @param      folderName  Name of the new folder
 * @param      container   Folder container class
 * @param      comment     Comment to attach
 *
 * @return     Response returned by the server
 */
Response<CreateFolderByPropertiesRequest> ExmdbQueries::createPublicFolder(const std::string& homedir, uint32_t domainId,
                                  const std::string& folderName, const std::string& container, const std::string& comment)
{
    auto acResponse = send<AllocateCnRequest>(homedir);
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
    return send<CreateFolderByPropertiesRequest>(homedir, 0, propvals);
}

/**
 * @brief      Delete public folder
 *
 * @param      homedir   Home directory path of the domain
 * @param      folderId  Id of the folder to delete
 *
 * @return     Response returned by the server
 */
SuccessResponse ExmdbQueries::deletePublicFolder(const std::string& homedir, uint64_t folderId)
{return send<DeleteFolderRequest>(homedir, 0, folderId, true);}

/**
 * @brief      Get list of public folder list owners
 *
 * @param      homedir   Home directory path of the domain
 * @param      folderId  ID of the folder
 *
 * @return     Response containing the owners. Can be converted to FolderOwnerListResponse for easier access.
 */
Response<QueryTableRequest> ExmdbQueries::getPublicFolderOwnerList(const std::string& homedir, uint64_t folderId)
{
    auto lptResponse = send<LoadPermissionTableRequest>(homedir, folderId);
    std::vector<uint32_t> proptags = {PropTag::MEMBERID, PropTag::MEMBERNAME, PropTag::MEMBERRIGHTS};
    auto qtResponse = send<QueryTableRequest>(homedir, "", 0, lptResponse.tableId, proptags, 0, lptResponse.rowCount);
    send<UnloadTableRequest>(homedir, lptResponse.tableId);
    return qtResponse;
}

/**
 * @brief      Add user to public folder owner list
 *
 * @param      homedir   Home directory path of the domain
 * @param      folderId  ID of the folder
 * @param      username  Username to add to list
 *
 * @return     Empty response if successful
 */
NullResponse ExmdbQueries::addFolderOwner(const std::string& homedir, uint64_t folderId, const std::string& username)
{
    uint32_t memberRights = Permission::READANY | Permission::CREATE | Permission::EDITANY | Permission::DELETEANY |
                            Permission::CREATESUBFOLDER | Permission::FOLDEROWNER | Permission::FOLDERCONTACT |
                            Permission::FOLDERVISIBLE;
    std::vector<TaggedPropval> propvals = {TaggedPropval(PropTag::SMTPADDRESS, username, false),
                                           TaggedPropval(PropTag::MEMBERRIGHTS, memberRights)};
    std::vector<PermissionData> permissions;
    permissions.emplace_back(PermissionData::ADD_ROW, propvals);
    return send<UpdateFolderPermissionRequest>(homedir, folderId, false, permissions);
}

/**
 * @brief      Remove member from owner list
 *
 * @param      homedir   Home directory path of the domain
 * @param      folderId  ID of the folder
 * @param      memberId  ID of the member to remove
 *
 * @return     Empty response if successful
 */
NullResponse ExmdbQueries::deleteFolderOwner(const std::string& homedir, uint64_t folderId, uint64_t memberId)
{
    std::vector<TaggedPropval> propvals = {TaggedPropval(PropTag::MEMBERID, memberId)};
    std::vector<PermissionData> permissions;
    permissions.emplace_back(PermissionData::REMOVE_ROW, propvals);
    return send<UpdateFolderPermissionRequest>(homedir, folderId, false, permissions);
}

/**
 * @brief      Modify store properties
 *
 * @param      homedir   Home directory path of the domain
 * @param      cpid      Unknown purpose
 * @param      propvals  PropertyValues to modify
 *
 * @return     Response containing a list of problems encountered
 */
ProblemsResponse ExmdbQueries::setStoreProperties(const std::string& homedir, uint32_t cpid,
                                                                     const std::vector<TaggedPropval>& propvals)
{return send<SetStorePropertiesRequest>(homedir, cpid, propvals);}

/**
 * @brief      Remove member from owner list
 *
 * @param      client    Client with active server connection
 * @param      homedir   Home directory path of the user
 *
 * @return     Empty response if successful
 */
NullResponse ExmdbQueries::unloadStore(const std::string& homedir)
{return send<UnloadStoreRequest>(homedir);}


/**
 * @brief      Modify folder properties
 *
 * @param      homedir   Home directory path of the domain
 * @param      cpid      Unknown purpose
 * @param      folderId  ID of the folder to modify
 * @param      propvals  PropertyValues to modify
 *
 * @return     Response containing a list of problems encountered
 */
ProblemsResponse ExmdbQueries::setFolderProperties(const std::string& homedir, uint32_t cpid, uint64_t folderID,
                                                   const std::vector<TaggedPropval>& propvals)
{return send<SetFolderPropertiesRequest>(homedir, cpid, folderID, propvals);}

}
