AC_INIT([admin-api], [0])
AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_MACRO_DIR([build-aux])
AC_PREFIX_DEFAULT([/usr])
AC_CONFIG_HEADERS([config.h])
AM_INIT_AUTOMAKE([1.10 foreign subdir-objects])
LT_INIT([disable-static])
m4_ifdef([AM_SILENT_RULES],[AM_SILENT_RULES([yes])])

AC_PROG_CC
AM_PROG_CC_C_O
AC_PROG_CXX
AC_PROG_INSTALL
dnl Needed, at the very least, for `make dist` (hence outside enable_base)
AX_PKG_SWIG_MAX(4, [], [ AC_MSG_ERROR([SWIG is required to build..]) ])

saved_CPPFLAGS="$CPPFLAGS"
saved_CFLAGS="$CFLAGS"
saved_CXXFLAGS="$CXXFLAGS"
saved_LDFLAGS="$LDFLAGS"
saved_LIBS="$LIBS"
AC_LANG_PUSH([C++])

my_CFLAGS="-Wall -Wmissing-declarations -Wwrite-strings"
my_CXXFLAGS="-Wall -Wmissing-declarations"
AC_MSG_CHECKING([available C++ standard])
cxxmode=""
for i in "c++17"; do
	CXXFLAGS="$saved_CXXFLAGS -std=$i"
	AC_COMPILE_IFELSE([AC_LANG_SOURCE([])], [cxxmode="$i"])
	AS_IF([test -n "$cxxmode"], [break])
done
CXXFLAGS="$saved_CXXFLAGS"
AS_IF([test -n "$cxxmode"], [
	my_CXXFLAGS="$my_CXXFLAGS -std=$cxxmode"
	AC_MSG_RESULT([$cxxmode])
], [
	AC_MSG_RESULT([none])
])

AC_ARG_WITH([unitdir],
	[AS_HELP_STRING([--with-unitdir=PATH], [Path to systemd service unit directory])],
	[unitdir="$withval"],
	[
		unitdir=$("$PKG_CONFIG" systemd --variable systemdsystemunitdir 2>/dev/null)
		AS_IF([test -z "$unitdir"], [unitdir='${prefix}/lib/systemd/system'])
	])
AC_SUBST([unitdir])

PKG_PROG_PKG_CONFIG
AS_IF([test -z "$PYTHON"], [PYTHON=python3])
AS_IF([test -n "$PYTHON"], [
	dnl Expand e.g. PYTHON="python3 -B" to PYTHON="/usr/bin/python3 -B"
	dnl (for embedding into #!), but keep unresolvable values as-is.
	set -- $PYTHON
	PYTHON=$(which "$1" 2>/dev/null)
	AS_IF([test -z "$PYTHON"], [PYTHON="$1"])
	shift
	PYTHON=$(echo "$PYTHON $@")
	PYTHON_MAJOR_VERSION=$($PYTHON -c "from __future__ import print_function;import sys;print(sys.version_info[[0]])" 2>/dev/null)
	PYTHON_MINOR_VERSION=$($PYTHON -c "from __future__ import print_function;import sys;print(sys.version_info[[1]])" 2>/dev/null)
])
PKG_CHECK_MODULES([python], [python-$PYTHON_MAJOR_VERSION.$PYTHON_MINOR_VERSION-embed], [], [
	PKG_CHECK_MODULES([python], [python-$PYTHON_MAJOR_VERSION.$PYTHON_MINOR_VERSION], [], [:])
])
AS_IF([test -n "$python_LIBS" || test -n "$PYTHON"], [AM_PATH_PYTHON([3.6])])

unitdir=$("$PKG_CONFIG" systemd --variable systemd_system_unit_dir 2>/dev/null)
tmpfilesdir=$("$PKG_CONFIG" systemd --variable tmpfilesdir 2>/dev/null)
AS_IF([test -z "$unitdir"], [unitdir='${prefix}/lib/systemd/system'])
AS_IF([test -z "$tmpfilesdir"], [tmpfilesdir='${prefix}/lib/tmpfiles.d'])
AC_SUBST([unitdir])
AC_SUBST([tmpfilesdir])

AC_DEFUN([MYSQL_WITH_MYSQL_CONFIG],[
	AC_PATH_PROGS([MYSQL_CONFIG], [mysql_config mariadb_config])
	AC_ARG_WITH([mysql-config], AS_HELP_STRING([--with-mysql-config=PATH], [path to the mysql-config script of mysql]),
		[MYSQL_CONFIG="$withval"])
	AS_IF([test -z "$MYSQL_CONFIG"], [AC_MSG_ERROR([mysql config program not found])])
	mysql_CFLAGS=$($MYSQL_CONFIG --include)
	mysql_LIBS=$($MYSQL_CONFIG --libs)
	mysql_VERSION=$($MYSQL_CONFIG --version) # see if it's there

	if test -z "$mysql_VERSION"; then
		AC_MSG_ERROR([Cannot find a mysql installation. Please use --with-mysql-config=PATH or install libmysqlclient-dev.])
	fi

	AC_SUBST([mysql_CFLAGS])
	AC_SUBST([mysql_LIBS])
	AC_SUBST([mysql_VERSION])
	AC_MSG_CHECKING([for MySQL includes])
	AC_MSG_RESULT([$mysql_CFLAGS])
	AC_MSG_CHECKING([for MySQL libs])
	AC_MSG_RESULT([$mysql_LIBS])
])
MYSQL_WITH_MYSQL_CONFIG

AC_SUBST([my_CFLAGS])
AC_SUBST([my_CXXFLAGS])
AS_IF([test -z "$cxxmode"], [AC_MSG_RESULT([*** No usable -std= argument was detected for this C++ compiler.])])
AC_LANG_POP([C++])
AC_CONFIG_FILES([Makefile exmdbpp/Makefile grommunio-dbconf/Makefile])
AC_OUTPUT
