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
