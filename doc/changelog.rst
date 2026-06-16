admin-api 1.20 (development)
============================

* Add endpoint to generate DKIM keypairs
* Enable and fix default/anonymous public folder permissions
* Fix 'anonymous' user folder permission deletion
* Unload mailbox store before deleting the user record to avoid orphaned files
* Deduplicate OpenAPI operation IDs to fix startup spec validation
* Fix 'bad escape sequence' warnings
* CLI: add units to more user properties


admin-api 1.19 (2026-05-27)
===========================

* Add endpoint to expose mailbox permissions
* Import altname from a configurable LDAP attribute
* Disable ldap3 schema fetching to fix objectGUID filter corruption
* Import LDAP org contacts only into the lowest domain to avoid GAB duplicates
* Skip the domain maxUser check when importing LDAP contacts
* Update group user membership on LDAP sync
* Delete user properties that are no longer present in LDAP
* Prevent deletion of vital user properties on LDAP sync
* Explicitly open LDAP connection to work around StartTLS failures with multiple servers
* CLI: add units to store size values
* CLI: fix user deletion prefix matching
* CLI: fix orphaned mailbox deletion
* CLI: fix `user show` output
* CLI: fix `user devices` helper texts
* CLI: drop underscore from matching wildcards
* Dashboard: handle missing or misbehaving systemd in containerized deployments
* Dashboard: skip malformed systemd unit blocks instead of crashing
* Dashboard: drop non-text entries from journal log output
* Dashboard: list g-keycloak in services and logs
* Convert the global DNS resolver to a singleton
* Fix startup crash when no internet connection is available
* Fix user folder permission delete
* Properly catch license credential errors
* Treat homeserver 0 as meaning "localhost"
* Return 503 instead of 500 when the chat service is unavailable
* Require the ``legacycrypt`` Python module (replaces stdlib ``crypt`` on Python 3.13+)


admin-api 1.18 (2026-02-17)
===========================

* Only count active users towards license limit
* Allow password change when logged in with altname
* Cope with capitalized user alias domains
* Add --disable-ldap argument to ldap reload
* Added authmgr handling for `cli ldap`
* Remove g-admin ldap reload -a arg for auth-backend
* Cease syncing named properties between user store and main DB


admin-api 1.17 (2025-02-17)
===========================

* CLI: add user subcommands `login`, `sendas`, `delegate`
* CLI: add json-kv and json-object formats
* CLI: add format argument for `store get` subcommand
* Add web/EAS/DAV privilege bits, setters and expressions
