# Configuring the API #
## General aspects ##
### How it works ###
Any YAML file placed in this directory will automatically be added to the configuration.
Files are read in alphabetical order. The parameters are updated using the following rules:
- If no parameter with this name exists, it is added
- If a parameter with this name already exists and
    - both are lists, they are concatenated
    - both are objects, they are merged
    - neither of the previous is true, it is overwritten.

## Available parameters ##
### Logging ###
(Changed in version `1.2`: The old, direct, configuration of the python logging has been removed.)  
Options regarding logging can be specified in the logging object. Currently only the log levels can be adjusted.  
Possible parameters:
- `level` (`int` or `string`, default: `WARNING`): Default log level (possible values are `DEBUG`, `INFO`, `WARNING`, `ERROR` and `CRITICAL`)
- `loggers` (`object`, default: `{}`): Associative array containing options for specific loggers

### Chat ###
Parameters necessary to make the grommunio-chat management work can be configured in the `chat` object.  
Possible parameters:
- `connection` (`object`): Parameters for connecting to the grommunio-chat API. See [Mattermost Driver](https://pypi.org/project/mattermostdriver/) for possible parameters.

### Database ###
Parameters necessary for database connection can be configured by the `DB` object.  
Possible parameters:
- `user` (`string`): User for database access
- `pass` (`string`): Password for user authentication
- `database` (`string`): Name of the database to connect to
- `host` (`string`, default: `127.0.0.1`): Host the database runs on
- `port` (`int`, default: `3306`): Port the database server runs on

### OpenAPI ###
The behavior of the OpenAPI validation can be configured by the `openapi` object.  
Possible parameters:
- `validateRequest` (`boolean`, default: `true`): Whether Request vaildation is enforced. If set to `true`, an invalid request will generate a HTTP 400 response. If set to `false`, the error will only be logged, but the request will be processed.
- `validateResponse` (`boolean`, default: `true`): Whether response validation is enforced. If set to `true`, an invalid response will be replace by a HTTP 500 response. If set to `false`, the error will only be logged and the invalid response is returned anyway.

### Logs ###
grommunio-admin can provide access to journald logs through the API. Accessible log files can be configured in the `logs` object.
Each entry in the `logs` object describes a log file. The name of the entry is the name used to acces the file throught the API.  
Possible parameters for each entry:
- `source` (`string`, required): Name of the systemd unit  

### Managed Configurations ###
Some configurations can be managed by grommunio-admin. Parameters can be configured by the `mconf` object.  
Possible parameters:
- `fileUid` (`string` or `int`): If set, change ownership of created configuration files to this user. Defaults to `options.fileUid` if omitted
- `fileGid` (`string` or `int`): If set, change ownership of created configuration files to this group. Defaults to `options.fileGid` if omitted
- `filePermissions` (`int`): If set, change file permissions of created configuration files to this bitmask. Defaults to `options.filePermissions` if omitted
- `ldapPath` (`string`): Path to the LDAP configuration file
- `authmgrPath` (`string`): Path to the authmgr configuration file

### Security ###
Parameters regarding security and authentication can be configured by the `security` object.  
Possible parameters:
- `jwtPrivateKeyFile` (`string`, default: `res/jwt-privkey.pem`): Path to the private RSA key file
- `jwtPublicKeyFile` (`string`, default: `res/jwt-pubkey.pem`): Path to the public RSA key file

### Sync ###
Some parameters determining how grommunio-admin connects to grommunio-sync can be adjusted in the `sync` object.  
Possible parameters:
- `host` (`string`, default `127.0.0.1`): Host running the Redis instance
- `port` (`int`, default `6379`): Port the Redis instance is listening on
- `db` (`string`, default `0`): Name of the Redis database
- `password` (`string`, default ``): Password to connect with
- `topTimestampKey` (`string`, default `grommunio-sync:topenabledat`): Key to write the current timestamp to
- `topdataKey` (`string`, default `grommunio-sync:topdata`): Key containing the top data hash
- `topExpireEnded` (`int`, default `20`): Time (in seconds) after which ended processes are removed
- `topExpireUpdate` (`int`, default `120`): Time (in seconds) since the last update after which processes are removed
- `syncStateFolder` (`string`, default `GS-SyncState`): Sub-folder containing the device sync states
- `policyHosts` (`list of strings`, default `["127.0.0.1", "localhost"]`): List of hosts that have unauthenticated access to user policies
- `defaultPolicy` (`object`): Overrides for the default Active Sync policy. For available values and defaults see `res/config.yaml`.

### Options ###
Further parameters can be set in the `options` object:  
- `dataPath` (`string`, default: `/usr/share/grommunio/common`): Directory where shared resources used by grommunio modules are stored
- `propnames` (`string`, default: `propnames.txt`): File containing the list of named properties, relative to `dataPath`
- `portrait` (`string`, default: `admin/api/portrait.jpg`): File containing the default portrait image, relative to `dataPath`
- `domainStoreRatio` (`int`, default: `10`): Mysterious storage factor for `domain.maxSize`
- `domainPrefix` (`string`, default: `/d-data/`): Prefix used for domain exmdb connections
- `userPrefix` (`string`, default: `/u-data/`): Prefix used for user exmdb connections
- `exmdbHost` (`string`, default: `::1`): Hostname of the exmdb service provider
- `exmdbPort` (`string`, default: `5000`): Port of the exmdb service provider
- `fileUid` (`string` or `int`): If set, change ownership of created files to this user
- `fileGid` (`string` or `int`): If set, change ownership of created files to this group
- `filePermissions` (`int`): If set, change file permissions of any created files to this bitmask
- `antispamUrl` (`string`, default: `http://127.0.0.1:11334`): URL of the grommunio-antispam backend
- `antispamEndpoints` (`list of strings`, default: `["stat", "graph", "errors"]`): List of allowed endpoints to proxy to grommunio-antispam
- `vhosts` (`object`, default: `{}`): Name -> URL mapping of nginx VHost status endpoints
