find_program(GZIP_LOCATION gzip DOC "Location of the gzip executable")

if(GZIP_LOCATION)
    set(GZIP_COMMAND ${GZIP_LOCATION} -c9)
    message(STATUS "gzip compression available")

    macro(compressed_name VARNAME)
        set(${VARNAME} ${ARGN})
        list(TRANSFORM ${VARNAME} PREPEND ${CMAKE_CURRENT_BINARY_DIR}/)
        list(TRANSFORM ${VARNAME} APPEND .gz)
    endmacro(compressed_name)

    function(compress_files)
        foreach(FILENAME ${ARGN})
            add_custom_command(
            OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${FILENAME}.gz
            COMMAND ${GZIP_COMMAND} ${CMAKE_CURRENT_SOURCE_DIR}/${FILENAME} > ${CMAKE_CURRENT_BINARY_DIR}/${FILENAME}.gz
            VERBATIM)
        endforeach()
    endfunction(compress_files)
else()
    message(STATUS "gzip compression unavailable")

    macro(compressed_name VARNAME)
        set(${VARNAME} ${ARGN})
        list(TRANSFORM ${VARNAME} PREPEND ${CMAKE_CURRENT_BINARY_DIR}/)
    endmacro(compressed_name)

    function(compress_files)
        foreach(FILENAME ${ARGN})
            add_custom_command(
            OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${FILENAME}
            COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_CURRENT_SOURCE_DIR}/${FILENAME} ${CMAKE_CURRENT_BINARY_DIR}/${FILENAME}
            VERBATIM)
        endforeach()
    endfunction(compress_files)
endif(GZIP_LOCATION)
