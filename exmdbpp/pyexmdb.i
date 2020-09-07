%module pyexmdb

#pragma SWIG nowarn=SWIGWARN_PARSE_NESTED_CLASS

%{
    #include "ExmdbClient.h"
    #include "queries.h"
    #include "structures.h"
%}

%include "std_string.i"
%include "std_except.i"
%include "std_vector.i"
%include "stdint.i"

%template(VI) std::vector<exmdbpp::structures::TaggedPropval>;
%template(VVI) std::vector<std::vector<exmdbpp::structures::TaggedPropval> >;

namespace exmdbpp
{

class ExmdbClient
{
public:
    ExmdbClient(const std::string&, uint16_t, const std::string&, bool) throw (std::runtime_error);
};


namespace structures
{

struct TaggedPropval
{
    TaggedPropval() = default;
    TaggedPropval(const TaggedPropval&);
    ~TaggedPropval();
    uint32_t tag;
    uint16_t type;
    std::string printValue() const;
    std::string toString() const;
};

}

namespace requests
{

struct NullResponse
{
    NullResponse() = default;
};

template<class Request>
struct Response : NullResponse
{
    Response() = default;
};

struct QueryTableRequest;
struct CreateFolderByPropertiesRequest;
struct DeleteFolderRequest;
struct DeleteFolderRequest;

%nodefaultctor;

template<>
struct Response<QueryTableRequest>
{
    std::vector<std::vector<structures::TaggedPropval> > entries;
};

template<>
struct Response<CreateFolderByPropertiesRequest>
{
    uint64_t folderId;
};

struct SuccessResponse
{
    bool success;
};

%clearnodefaultctor;

%template(QueryTableResponse) requests::Response<requests::QueryTableRequest>;
%template(CreateFolderByPropertiesResponse) requests::Response<requests::CreateFolderByPropertiesRequest>;
%template(DeleteFolderResponse) requests::Response<requests::DeleteFolderRequest>;

}

namespace queries
{

struct Folder
{
    uint64_t folderId;
    std::string displayName;
    std::string comment;
    uint64_t creationTime;
};

struct FolderListResponse
{
    struct Folder
    {
        uint64_t folderId;
        std::string displayName;
        std::string comment;
        uint64_t creationTime;
    };

    FolderListResponse(const requests::Response<requests::QueryTableRequest>&);

    std::vector<queries::Folder> folders;
};

struct Owner
{
    uint64_t memberId;
    std::string memberName;
    uint32_t memberRights;
};

struct FolderOwnerListResponse
{
    struct Owner
    {
        uint64_t memberId;
        std::string memberName;
        uint32_t memberRights;
    };

    FolderOwnerListResponse(const requests::Response<requests::QueryTableRequest>&);

    std::vector<queries::Owner> owners;
};

requests::Response<requests::QueryTableRequest> getFolderList(ExmdbClient&, const std::string&) throw (std::runtime_error, std::out_of_range);
requests::Response<requests::CreateFolderByPropertiesRequest> createPublicFolder(ExmdbClient&, const std::string&, uint32_t, const std::string&, const std::string&, const std::string&) throw (std::runtime_error, std::out_of_range);
requests::SuccessResponse deletePublicFolder(ExmdbClient&, const std::string&, uint64_t) throw (std::runtime_error, std::out_of_range);
requests::Response<requests::QueryTableRequest> getPublicFolderOwnerList(ExmdbClient&, const std::string&, uint64_t) throw (std::runtime_error, std::out_of_range);
requests::NullResponse addFolderOwner(ExmdbClient&, const std::string&, uint64_t, const std::string&) throw (std::runtime_error, std::out_of_range);
requests::NullResponse deleteFolderOwner(ExmdbClient&, const std::string&, uint64_t, uint64_t) throw (std::runtime_error, std::out_of_range);

}

}

%{
namespace exmdbpp::queries
{
    typedef FolderListResponse::Folder Folder;
    typedef FolderOwnerListResponse::Owner Owner;
}
%}

%template(VFolder) std::vector<exmdbpp::queries::Folder>;
%template(VOwner) std::vector<exmdbpp::queries::Owner>;
