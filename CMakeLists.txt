cmake_minimum_required(VERSION 3.14)
project(grommunio-admin VERSION 1.4 LANGUAGES NONE)

include(GNUInstallDirs)
include(data/gzip.cmake)

find_package(PkgConfig REQUIRED)

set(COMMONCONFDIR ${CMAKE_INSTALL_FULL_SYSCONFDIR}/grommunio-admin-common)
set(COMMONDIR ${CMAKE_INSTALL_FULL_DATADIR}/grommunio-admin-common)
set(CONFDIR ${CMAKE_INSTALL_FULL_SYSCONFDIR}/grommunio-admin-api)
set(INSTALLDIR ${CMAKE_INSTALL_FULL_DATADIR}/grommunio-admin-api)
set(NGINXDIR ${COMMONDIR}/nginx.d)
pkg_get_variable(TMPFILESDIR systemd tmpfilesdir)
pkg_get_variable(UNITDIR systemd systemdsystemunitdir)

set(MANFILES doc/man/grommunio-admin.1 doc/man/grommunio-admin-config.1 doc/man/grommunio-admin-connect.1 doc/man/grommunio-admin-dbconf.1 doc/man/grommunio-admin-domain.1 doc/man/grommunio-admin-fetchmail.1 doc/man/grommunio-admin-fs.1 doc/man/grommunio-admin-ldap.1 doc/man/grommunio-admin-mconf.1 doc/man/grommunio-admin-mlist.1 doc/man/grommunio-admin-passwd.1 doc/man/grommunio-admin-run.1 doc/man/grommunio-admin-service.1 doc/man/grommunio-admin-shell.1 doc/man/grommunio-admin-taginfo.1 doc/man/grommunio-admin-user.1 doc/man/grommunio-admin-version.1)
file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/doc/man)
compressed_name(MANPAGES ${MANFILES})
compress_files(${MANFILES})
add_custom_target(man ALL DEPENDS ${MANPAGES})

add_custom_command(
            OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/openapi.json
            COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/data/yaml2json.py ${CMAKE_CURRENT_SOURCE_DIR}/res/openapi.yaml ${CMAKE_CURRENT_BINARY_DIR}/openapi.json
                    || echo "Failed to create openapi.json - falling back to YAML"
            VERBATIM)

add_custom_target(openapi ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/openapi.json)

file(CREATE_LINK ${INSTALLDIR}/main.py grommunio-admin SYMBOLIC)

install(FILES ${MANPAGES} DESTINATION ${CMAKE_INSTALL_MANDIR}/man1)
install(DIRECTORY api cli endpoints orm services tools DESTINATION ${INSTALLDIR})
install(DIRECTORY res DESTINATION ${INSTALLDIR})
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/openapi.json DESTINATION ${INSTALLDIR}/res OPTIONAL)
install(PROGRAMS main.py DESTINATION ${INSTALLDIR})
install(FILES data/api-config.ini data/config.yaml DESTINATION ${INSTALLDIR})
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/grommunio-admin TYPE SBIN)

install(DIRECTORY DESTINATION ${CONFDIR}/conf.d)
install(DIRECTORY DESTINATION ${COMMONCONFDIR}/license)
install(FILES data/api.conf DESTINATION ${NGINXDIR})

install(FILES data/autocomplete.sh DESTINATION ${CMAKE_INSTALL_FULL_DATADIR}/bash-completion/completions RENAME grommunio-admin)
install(FILES data/grommunio-admin-api.service data/grommunio-admin-api.socket DESTINATION ${UNITDIR})
install(FILES data/portrait.jpg DESTINATION ${COMMONDIR})
install(FILES data/tmpfiles-grommunio-admin-api.conf DESTINATION ${TMPFILESDIR} RENAME grommunio-admin-api.conf)
