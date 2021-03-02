/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2021 grammm GmbH
 */
#include <algorithm>
#include <array>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <mysql/mysql.h>

using namespace std;

const char* gromoxMysqlCfgPath = "/etc/gromox/mysql_adaptor.cfg";

/**
 * @brief      Helper struct to automatically free mysql resources
 */
struct mysql_free
{
    void operator()(MYSQL* conn) {mysql_close(conn);}
    void operator()(MYSQL_RES* res) {mysql_free_result(res);}
};

using mysqlconn_t = unique_ptr<MYSQL, mysql_free>;
using mysqlres_t = unique_ptr<MYSQL_RES, mysql_free>;

enum {Command = 0, Service, File, Key, Value}; ///< Positional parameter index

array<string, 5> args; ///< Positional arguments
bool init = false; ///< --init flag set
int verbosity = 0;  ///< Count of verbose flags

/**
 * @brief      Print help message and exit
 *
 * @param      name  Program name (argv[0])
 */
[[noreturn]] void printHelp(const char* name)
{
    cerr << "grammm database configuration management tool\n"
            "Usage:\n"
         "\t" << name << " set [(-i | --init)] [(-v | --verbose)] [--] <service> <file> <key> [<value>]\n"
         "\t" << name << " get [(-v | --verbose)] [--] <service> <file> [<key>]\n"
         "\t" << name << " delete [(-v | --verbose)] [--] <service> [<file> [<key>]]\n"
         "\t" << name << " (-h | --help)\n"
         "\nOptional arguments:\n"
         "\t-h\t--help\t    Print this help and exit\n"
         "\t-i\t--init\t    Only set variable if it does not exist, otherwise exit with error\n"
         "\t-v\t--verbose   Increase verbosity level (max 2)\n"
         "\t--\t\t    Consider every following argument to be positional\n";
    exit(0);
}

/**
 * @brief      Print error message
 *
 * @param      msg   Message to print
 *
 * @return     Always `false`
 */
bool argerr(const char* msg)
{
    cerr << msg << " Use -h for usage information.\n";
    return false;
}

/**
 * @brief      Parse command line parameters
 *
 * @param      argv  Command line arguments
 *
 * @return     `true` if successful, `false` otherwise
 */
bool parseCommandLine(char** argv)
{
    int nargs = 0;
    bool commandsOnly = false;
    for(char** argp = argv+1; *argp != nullptr; ++argp)
    {
        char* arg = *argp;
        if(!commandsOnly && *arg == '-')
        {
            if(*(++arg) == '-')
            {
                ++arg;
                if(!strcmp(arg, "help"))
                    printHelp(*argv);
                else if(!strcmp(arg, "init"))
                    init = true;
                else if(!strcmp(arg, "verbose"))
                    ++verbosity;
                else if(!*arg)
                    commandsOnly = true;
                else
                {
                    cerr << "Unknown option '" << arg << "'\n";
                    return false;
                }
            }
            else
                for(char* sopt = arg; *sopt; ++sopt)
                {
                    switch(*sopt)
                    {
                    case 'h':
                        printHelp(*argv); break;
                    case 'i':
                        init = true; break;
                    case 'v':
                        ++verbosity; break;
                    default:
                        cerr << "Unknown short option '" << *sopt << "'\n";
                    }
                }
        }
        else if(nargs >= 5)
            return argerr("Too many arguments.");
        else
            args[nargs++] = arg;
    }
    if(nargs == 0)
        return argerr("Missing command.");
    if(args[Command] == "set")
    {
        if(nargs < 4)
            return argerr("Too few arguments.");
    }
    else if(args[Command] == "get")
    {
        if(nargs < 3)
            return argerr("Too few arguments.");
        if(nargs > 4)
            return argerr("Too many arguments.");
    }
    else if(args[Command] == "delete")
    {
        if(nargs < 2)
            return argerr("Too few arguments.");
        if(nargs > 4)
            return argerr("Too many arguments.");
    }
    else
        return argerr("Unknown command.");
    return true;
}

/**
 * @brief      Get MySQL connection
 *
 * Tries to read `./mysql_adaptor.conf` or `/etc/gromox/mysql_adaptor.cfg`
 * to determine connection parameters.
 *
 * @return     Connection object or `nullptr` on error.
 */
MYSQL* getMysql()
{
    fstream file;
    string host, user, passwd, db, port, line;
    if(verbosity >= 2)
        cerr << "Opening 'mysql_adaptor.cfg'...\n";
    file.open("mysql_adaptor.cfg");
    if(!file.is_open())
    {
        if(verbosity >= 2)
            cerr << "Failed. Trying '" << gromoxMysqlCfgPath << "'\n";
        file.open(gromoxMysqlCfgPath);
        if(!file.is_open())
        {
            if(verbosity)
                cerr << "Could not open configuration file.\n";
            return nullptr;
        }
    }
    string key, value;
    while(getline(file, line))
    {
        size_t eqpos;
        if((eqpos = line.find("=")) == string::npos)
            continue;
        key = line.substr(0, eqpos);
        value = line.substr(eqpos+1);
        key.erase(remove_if(key.begin(), key.end(), iswspace), key.end());
        value.erase(remove_if(value.begin(), value.end(), iswspace), value.end());
        if(key == "MYSQL_HOST")
            host = std::move(value);
        else if(key =="MYSQL_PORT")
            port = std::move(value);
        else if(key == "MYSQL_USERNAME")
            user = std::move(value);
        else if(key == "MYSQL_PASSWORD")
            passwd = std::move(value);
        else if(key == "MYSQL_DBNAME")
            db = std::move(value);
    }
    unsigned int iport;
    try
        {iport = stoul(port);}
    catch(const invalid_argument&)
        {return nullptr;}
    if(verbosity >= 2)
        cerr << "MySQL connection parameters: " << user << ":" << passwd << "@" << host << ":" << iport << "/" << db << endl;
    MYSQL* conn = mysql_init(nullptr);
    if(mysql_real_connect(conn, host.c_str(), user.c_str(), passwd.c_str(), db.c_str(), iport, nullptr, 0))
       return conn;
    mysql_close(conn);
    return nullptr;
}

/**
 * @brief      Create quoted arguments
 *
 * @param      conn  MySQL connection
 */
void prepareArgs(mysqlconn_t& conn)
{
    for(string& arg : args)
    {
        char temp[arg.length()*2+1];
        mysql_real_escape_string(conn.get(), temp, arg.c_str(), arg.length());
        arg = temp;
    }
}


int grammmConfSet(mysqlconn_t& mconn)
{
    static const int QLEN = 4096, FLEN = 2048;
    char query[QLEN];
    char filter[FLEN];
    MYSQL* conn = mconn.get();
    if(snprintf(filter, FLEN, "WHERE `service`='%s' AND `file`='%s' AND `key`='%s'",
                args[Service].c_str(), args[File].c_str(), args[Key].c_str()) >= FLEN)
        return 101;
    if(snprintf(query, QLEN, "SELECT value FROM `configs` %s", filter) >= QLEN)
        return 102;
    if(mysql_query(conn, query))
        return 103;
    mysqlres_t res(mysql_store_result(conn));
    if(mysql_num_rows(res.get()))
    {
        if(init)
        {
            MYSQL_ROW row = mysql_fetch_row(res.get());
            if(row[0] != args[Value])
            {
                cerr << "Key exists - aborted.\n";
                return 104;
            }
        }
        if(snprintf(query, QLEN, "UPDATE `configs` SET `value`='%s' %s", args[Value].c_str(), filter) >= QLEN)
            return 105;
    }
    else
        if(snprintf(query, QLEN, "INSERT INTO `configs` (`service`, `file`, `key`, `value`) VALUES  ('%s', '%s', '%s', '%s')",
                    args[Service].c_str(), args[File].c_str(), args[Key].c_str(), args[Value].c_str()) >= QLEN)
            return 106;
    if(mysql_query(conn, query))
        return 107;
    return 0;
}


int grammmConfGet(mysqlconn_t& conn)
{
    static const int QLEN = 4096;
    char query[QLEN];
    int pos = snprintf(query, QLEN, "SELECT `key`, `value` FROM `configs` WHERE `service`='%s' AND `file`='%s'",
                       args[Service].c_str(), args[File].c_str());
    if(pos >= QLEN)
        return 201;
    if(!args[Key].empty() && snprintf(query+pos, QLEN-pos, " AND `key`='%s'", args[Key].c_str()) >= QLEN-pos)
        return 202;
    if(mysql_query(conn.get(), query))
        return 203;
    mysqlres_t res(mysql_store_result(conn.get()));
    for(my_ulonglong i = 0; i < mysql_num_rows(res.get());++i)
    {
        MYSQL_ROW row = mysql_fetch_row(res.get());
        cout << row[0] << "=" << row[1] << endl;
    }
    return 0;
}


int grammmConfDel(mysqlconn_t& conn)
{
    static const int QLEN = 4096;
    char query[QLEN];
    int pos = snprintf(query, QLEN, "DELETE FROM `configs` WHERE `service`='%s'", args[Service].c_str());
    if(pos >= QLEN)
        return 301;
    if(!args[File].empty())
    {
        if((pos += snprintf(query+pos, QLEN-pos, " AND `file`='%s'", args[File].c_str())) >= QLEN)
            return 302;
    }
    if(!args[Key].empty())
    {
        if(snprintf(query+pos, QLEN-pos, " AND `key`='%s'", args[Key].c_str()) >= QLEN-pos)
            return 303;
    }
    if(mysql_query(conn.get(), query))
        return 304;
    if(verbosity)
    {
        int n = mysql_affected_rows(conn.get());
        cerr << n << " key" << (n != 1? "s" : "") << " deleted\n";
    }
    return 0;
}


int main(int argc, char** argv)
{
    if(argc == 0 || !parseCommandLine(argv))
        return 1;
    mysqlconn_t conn(getMysql());
    if(!conn)
    {
        cerr << "Could not connect to MySQL server.\n";
        return 2;
    }
    prepareArgs(conn);
    int res = 1000;
    if(args[Command] =="set")
        res = grammmConfSet(conn);
    else if(args[Command] == "get")
        res =  grammmConfGet(conn);
    else if(args[Command] == "delete")
        res = grammmConfDel(conn);
    if(verbosity)
    {
        if(res)
            cerr << "Error (" << res << ")\n";
        else
            cerr << "Success.\n";
    }
    return res;
}
