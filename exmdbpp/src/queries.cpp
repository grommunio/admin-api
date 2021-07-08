/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2020 grammm GmbH
 */
#include "queries.h"
#include "util.h"
#include "constants.h"
#include "IOBufferImpl.h"

using namespace exmdbpp::constants;
using namespace exmdbpp::requests;
using namespace exmdbpp::structures;

namespace exmdbpp::queries
{

const std::vector<uint32_t> ExmdbQueries::defaultFolderProps =
{PropTag::FOLDERID, PropTag::DISPLAYNAME, PropTag::COMMENT, PropTag::CREATIONTIME, PropTag::CONTAINERCLASS};

/**
 * @brief      Load propvals into predefined fields
 *
 * @param      propvals     List of TaggedPropvals
 */
Folder::Folder(const std::vector<TaggedPropval>& propvals)
{init(propvals);}


/**
 * @brief      Folder response into predefined fields
 *
 * @param      response     Response to convert
 */
Folder::Folder(const PropvalResponse& response)
{init(response.propvals);}

/**
 * @brief     Initialize from tagged propval array
 *
 * @param      propvals     List of TaggedPropvals
 */
void Folder::init(const std::vector<structures::TaggedPropval>& propvals)
{
    for(const TaggedPropval& tp : propvals)
    {
        switch(tp.tag)
        {
        case PropTag::FOLDERID:
            folderId = tp.value.u64; break;
        case PropTag::DISPLAYNAME:
            displayName = tp.value.str; break;
        case PropTag::COMMENT:
            comment = tp.value.str; break;
        case PropTag::CREATIONTIME:
            creationTime = tp.value.u64; break;
        case PropTag::CONTAINERCLASS:
            container = tp.value.str; break;
        }
    }
}

/**
 * @brief      Interpret query table response as folder list
 *
 * @param      response  Response to convert
 */
FolderListResponse::FolderListResponse(const Response_t<QueryTableRequest>& response)
{
    folders.reserve(response.entries.size());
    for(auto& entry : response.entries)
         folders.emplace_back(entry);
}

/**
 * @brief      Interpret query table response as folder owner list
 *
 * @param      response  Response to convert
 */
FolderOwnerListResponse::FolderOwnerListResponse(const Response_t<QueryTableRequest>& response)
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

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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
Response_t<QueryTableRequest> ExmdbQueries::getFolderList(const std::string& homedir, const std::vector<uint32_t>& proptags)
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
Response_t<CreateFolderByPropertiesRequest> ExmdbQueries::createFolder(const std::string& homedir, uint32_t domainId,
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

    xid.writeXID(tmpbuff);
    propvals.emplace_back(PropTag::CHANGEKEY, tmpbuff.data(), false);

    size_t offset = tmpbuff.tell();
    tmpbuff.push(xid);
    propvals.emplace_back(PropTag::PREDECESSORCHANGELIST, tmpbuff.data()+offset, false);
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
SuccessResponse ExmdbQueries::deleteFolder(const std::string& homedir, uint64_t folderId)
{return send<DeleteFolderRequest>(homedir, 0, folderId, true);}

/**
 * @brief      Get list of public folder list owners
 *
 * @param      homedir   Home directory path of the domain
 * @param      folderId  ID of the folder
 *
 * @return     Response containing the owners. Can be converted to FolderOwnerListResponse for easier access.
 */
TableResponse ExmdbQueries::getFolderOwnerList(const std::string& homedir, uint64_t folderId)
{
    auto lptResponse = send<LoadPermissionTableRequest>(homedir, folderId, 0);
    uint32_t proptags[] = {PropTag::MEMBERID, PropTag::MEMBERNAME, PropTag::MEMBERRIGHTS};
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
    PermissionData permissions[] = {PermissionData(PermissionData::ADD_ROW, propvals)};
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
    PermissionData permissions[] = {PermissionData(PermissionData::REMOVE_ROW, propvals)};
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
ProblemsResponse ExmdbQueries::setFolderProperties(const std::string& homedir, uint32_t cpid, uint64_t folderId,
                                                   const std::vector<TaggedPropval>& propvals)
{return send<SetFolderPropertiesRequest>(homedir, cpid, folderId, propvals);}

/**
 * @brief      Get folder properties
 *
 * @param      homedir   Home directory path of the domain
 * @param      cpid      Unknown purpose
 * @param      folderId  ID of the folder to get
 * @param      propvals  PropertyValues to get
 *
 * @return     Response containing a list of problems encountered
 */
PropvalResponse ExmdbQueries::getFolderProperties(const std::string& homedir, uint32_t cpid, uint64_t folderId,
                                                                       const std::vector<uint32_t>& proptags)
{return send<GetFolderPropertiesRequest>(homedir, cpid, folderId, proptags);}

/**
 * @brief      Get store properties
 *
 * @param      homedir   Home directory path of the domain
 * @param      cpid      Unknown purpose
 * @param      propvals  PropertyValues to modify
 *
 * @return     Response containing a list of problems encountered
 */
PropvalResponse ExmdbQueries::getStoreProperties(const std::string& homedir, uint32_t cpid,
                                                                       const std::vector<uint32_t>& proptags)
{return send<GetStorePropertiesRequest>(homedir, cpid, proptags);}

/**
 * @brief      Get all store proptags
 *
 * @param      homedir   Home directory path of the domain
 *
 * @return     Response containing a list prop tags
 */
Response_t<GetAllStorePropertiesRequest> ExmdbQueries::getAllStoreProperties(const std::string& homedir)
{return send<GetAllStorePropertiesRequest>(homedir);}

/**
 * @brief      Remove store properties
 *
 * @param      homedir   Home directory path of the domain
 * @param      proptags  Properties to remove
 *
 * @return     Empty response if successful
 */
NullResponse ExmdbQueries::removeStoreProperties(const std::string& homedir, const std::vector<uint32_t>& proptags)
{return send<RemoveStorePropertiesRequest>(homedir, proptags);}


/**
 * @brief       Get grammm-sync state for user
 *
 * @param       homedir     Home directory path of the user
 * @param       folderName  Name of the folder containing sync data
 *
 * @return      Map of devices and their state
 */
SyncData ExmdbQueries::getSyncData(const std::string& homedir, const std::string& folderName)
{
    uint64_t parentFolderID = util::makeEidEx(1, PublicFid::ROOT);
    uint32_t fidTag[] = {PropTag::FOLDERID, PropTag::DISPLAYNAME};
    uint32_t bodyTag[] = {PropTag::BODY};
    uint32_t midTag[] = {PropTag::MID};
    Restriction ddFilter = Restriction::PROPERTY(Restriction::EQ, 0, TaggedPropval(PropTag::DISPLAYNAME, "devicedata"));

    SyncData data;

    auto folder = send<GetFolderByNameRequest>(homedir, parentFolderID, folderName);
    auto subfolders = send<LoadHierarchyTableRequest>(homedir, folder.folderId, "", 0);
    data.reserve(subfolders.rowCount);
    auto subfolderIDs = send<QueryTableRequest>(homedir, "", 0, subfolders.tableId, fidTag, 0, subfolders.rowCount);
    send<UnloadTableRequest>(homedir, subfolders.tableId);
    for(const auto& subfolder: subfolderIDs.entries)
    {
        if(subfolder.size() != 2 || subfolder[0].tag != PropTag::FOLDERID || subfolder[1].tag != PropTag::DISPLAYNAME)
            continue;
        auto content = send<LoadContentTableRequest>(homedir, 0, subfolder[0].value.u64, "", 2, ddFilter);
        auto table = send<QueryTableRequest>(homedir, "", 0, content.tableId, midTag, 0, content.rowCount);
        send<UnloadTableRequest>(homedir, content.tableId);
        if(table.entries.empty())
            continue;
        if(table.entries.empty())
            continue;
        auto& msgobject = table.entries[0];
        if(msgobject.size() != 1 || msgobject[0].tag != PropTag::MID)
            continue;
        auto message = send<GetMessagePropertiesRequest>(homedir, "", 0, msgobject[0].value.u64, bodyTag);
        if(message.propvals.size() != 1 || message.propvals[0].tag != PropTag::BODY)
            continue;
        data.emplace(subfolder[1].value.str, message.propvals[0].value.str);
    }
    return data;
}

/**
 * @brief       Initiate device resync
 *
 * Deletes the device sync folder, causing the device to re-sync.
 *
 * @param       homedir     Home directory path of the user
 * @param       folderName  Name of the folder containing sync data
 * @param       deviceId    Device ID string
 */
void ExmdbQueries::resyncDevice(const std::string& homedir, const std::string& folderName, const std::string& deviceId)
{
    uint64_t rootFolderId = util::makeEidEx(1, PublicFid::ROOT);
    auto syncFolder = send<GetFolderByNameRequest>(homedir, rootFolderId, folderName);
    auto deviceFolder = send<GetFolderByNameRequest>(homedir, syncFolder.folderId, deviceId);
    send<EmptyFolderRequest>(homedir, 0, "", deviceFolder.folderId, true, false, true, false);
}

}
