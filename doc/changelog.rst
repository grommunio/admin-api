admin-api 1.22 (development)
============================

* The API sets the session cookie (HttpOnly, SameSite=Strict), scripts on
  other services of the host can no longer read the admin token
* New ``POST /logout`` endpoint, revokes the token (uses redis)
* Organization admins no longer pass read-only system admin checks and lose
  access to system-wide data (``/system`` endpoints such as roles, logs,
  dbconf or the LDAP configuration, tasks of other organizations).
  ``GET /system/users`` remains available to them, limited to the users of
  the administrated organization given as ``orgID``.
* Security: only system admins can grant or revoke grommunio-chat admin
  permissions (``chatAdmin``). As grommunio-chat is shared by all domains, the
  attribute is ignored for domain and organization admins.
* Security: the API and the creation defaults no longer accept the ID of an
  existing chat account as ``chat`` value, linking chat accounts is left to
  the CLI (``user create`` / ``user modify`` with ``--chat <ID>``)
* Fix live status (``/system/vhostStatus``) failing with a 502 error
* Domain and organization admins can only reset passwords
  (``PUT /passwd/<username>``) and list users (``GET /users``) of their own
  domains. The ``ResetPasswd`` permission is no longer implied by
  ``DomainAdmin`` and ``OrgAdmin`` and has to be granted explicitly to reset
  users system-wide.
* ``PUT /passwd/<username>`` no longer resets the password of the caller
  (use ``PUT /passwd`` with the old password instead) and rejects a missing
  or non-string ``new`` with 400
* Security: the address an e-mail forward applies to can no longer be set
  through the API, it always is the address of the user the forward belongs
  to. Forwards require a user with a mail address (no contacts), and existing
  users cannot be renamed to a name without domain part.
* Renaming a user keeps its e-mail forward. Purging a domain removes the
  forwards of its addresses, and a forward left behind on an address is
  removed when the address is given to a user (created or renamed) or added
  as an alias.


admin-api 1.21 (development)
============================

* CLI: new ``passwd --password-stdin`` option that reads the password from
  stdin. Unlike ``--password``, it does not expose the password in the
  process list, where any local user can read it from ``/proc``.
* Single sign-on login via OpenID Connect (``GET /login/oidc``). The ``oidc``
  configuration section is written by grommunio-auth.


admin-api 1.20 (2026-06-16)
===========================

* Add endpoint to generate DKIM keypairs
* Enable and fix default/anonymous public folder permissions
* Fix 'anonymous' user folder permission deletion
* Unload mailbox store before deleting the user record to avoid orphaned files
* Deduplicate OpenAPI operation IDs to fix startup spec validation
* Fix 'bad escape sequence' warnings
* CLI: add units to more user properties
* Fix malformed LDAP filter when group DN contains filter metacharacters
* Escape domain names in LDAP user search filter as defense in depth


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
