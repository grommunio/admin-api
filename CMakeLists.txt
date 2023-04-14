cmake_minimum_required(VERSION 3.14)
project(grommunio-admin VERSION 1.11 LANGUAGES NONE)

include(GNUInstallDirs)

find_package(PkgConfig REQUIRED)

set(COMMONCONFDIR ${CMAKE_INSTALL_FULL_SYSCONFDIR}/grommunio-admin-common)
set(COMMONDIR ${CMAKE_INSTALL_FULL_DATADIR}/grommunio-admin-common)
set(CONFDIR ${CMAKE_INSTALL_FULL_SYSCONFDIR}/grommunio-admin-api)
set(INSTALLDIR ${CMAKE_INSTALL_FULL_DATADIR}/grommunio-admin-api)
set(NGINXDIR ${COMMONDIR}/nginx.d)
pkg_get_variable(TMPFILESDIR systemd tmpfilesdir)
pkg_get_variable(UNITDIR systemd systemdsystemunitdir)

add_custom_command(
            OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/openapi.json
            COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/data/yaml2json.py ${CMAKE_CURRENT_SOURCE_DIR}/res/openapi.yaml ${CMAKE_CURRENT_BINARY_DIR}/openapi.json
                    || echo "Failed to create openapi.json - falling back to YAML"
            VERBATIM)

add_custom_target(openapi ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/openapi.json)

file(CREATE_LINK ${INSTALLDIR}/main.py ${CMAKE_CURRENT_BINARY_DIR}/grommunio-admin SYMBOLIC)

install(DIRECTORY doc/man/ DESTINATION ${CMAKE_INSTALL_MANDIR}/man1)
install(DIRECTORY api cli endpoints orm services tools DESTINATION ${INSTALLDIR})
install(DIRECTORY res DESTINATION ${INSTALLDIR})
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/openapi.json DESTINATION ${INSTALLDIR}/res OPTIONAL)
install(PROGRAMS main.py DESTINATION ${INSTALLDIR})
install(FILES data/api-config.ini data/config.yaml DESTINATION ${INSTALLDIR})
install(FILES data/polkit-10-grommunio.rules DESTINATION ${CMAKE_INSTALL_FULL_DATADIR}/polkit-1/rules.d RENAME 10-grommunio.rules)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/grommunio-admin TYPE SBIN)

install(DIRECTORY DESTINATION ${CMAKE_INSTALL_FULL_LOCALSTATEDIR}/lib/grommunio-admin-api DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE)
install(DIRECTORY DESTINATION ${CONFDIR}/conf.d)
install(DIRECTORY DESTINATION ${COMMONCONFDIR}/license)
install(FILES data/api.conf DESTINATION ${NGINXDIR})

install(FILES data/autocomplete.sh DESTINATION ${CMAKE_INSTALL_FULL_DATADIR}/bash-completion/completions RENAME grommunio-admin)
install(FILES data/grommunio-admin-api.service data/grommunio-admin-api.socket DESTINATION ${UNITDIR})
install(FILES data/portrait.jpg DESTINATION ${COMMONDIR})
install(FILES data/tmpfiles-grommunio-admin-api.conf DESTINATION ${TMPFILESDIR} RENAME grommunio-admin-api.conf)
install(FILES data/grommunio-sudo DESTINATION ${CMAKE_INSTALL_FULL_SYSCONFDIR}/sudoers.d)
