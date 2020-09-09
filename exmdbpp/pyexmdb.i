%module pyexmdb

%warnfilter(325) Folder;
%warnfilter(325) Owner;

%{
    #include "ExmdbClient.h"
    #include "queries.h"
    #include "structures.h"

    namespace exmdbpp::structures
    {
        TaggedPropval TaggedPropval_u64(uint32_t tag, uint64_t value)
        {return TaggedPropval(tag, value);}
    }
%}

%include "std_string.i"
%include "std_except.i"
%include "std_vector.i"
%include "stdint.i"

%template(VTaggedPropval) std::vector<exmdbpp::structures::TaggedPropval>;
%template(VVTaggedPropval) std::vector<std::vector<exmdbpp::structures::TaggedPropval> >;
%template(VPropertyProblem) std::vector<exmdbpp::structures::PropertyProblem>;

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

struct PropertyProblem
{
    PropertyProblem() = default;

    uint16_t index;
    uint32_t proptag;
    uint32_t err;
};

TaggedPropval TaggedPropval_u64(uint32_t, uint64_t);

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
struct SetStorePropertiesRequest;

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

template<>
struct Response<SetStorePropertiesRequest>
{
    std::vector<structures::PropertyProblem> problems; ///< List of problems that occured when setting store values
};

%clearnodefaultctor;

%template(QueryTableResponse) requests::Response<requests::QueryTableRequest>;
%template(CreateFolderByPropertiesResponse) requests::Response<requests::CreateFolderByPropertiesRequest>;
%template(DeleteFolderResponse) requests::Response<requests::DeleteFolderRequest>;
%template(SetStorePropertiesResponse) requests::Response<requests::SetStorePropertiesRequest>;

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
requests::Response<requests::SetStorePropertiesRequest> setStoreProperties(ExmdbClient&, const std::string&, uint32_t, const std::vector<structures::TaggedPropval>&);
requests::NullResponse unloadStore(ExmdbClient&, const std::string&);

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
