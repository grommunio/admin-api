/*
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * SPDX-FileCopyrightText: 2021 grommunio GmbH
 */
#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_set>
#include <unordered_map>

#include <mysql.h>

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

enum Arg : uint8_t {Command = 0, Service, File, Key, Value}; ///< Positional parameter index

uint8_t nargs = 0;
array<string, 5> args; ///< Positional arguments
bool init = false; ///< --init flag set
bool batch = false; ///< --batch flag set
int verbosity = 0;  ///< Count of verbose flags


unordered_set<string> keyCommits = {"postconf -e $ENTRY"};
unordered_set<string> fileCommits = {};
unordered_set<string> serviceCommits = {"systemctl reload $SERVICE", "systemctl restart $SERVICE"};
enum CmdLevel : uint8_t {CMD_SERVICE, CMD_FILE, CMD_KEY};
const char* cmdTarget[] = {"commit_service", "commit_file", "commit_key"};

inline bool hasArg(Arg arg)
{return nargs > arg;}

/**
 * @brief      Get commit command level index by key
 *
 * @param      target  Config key identifying the command
 *
 * @return     Index or -1 if not found
 */
inline int cmdLevel(const char* target)
{
    for(int i = 0; i < 3; ++i)
        if(!strcmp(target, cmdTarget[i]))
            return i;
    return -1;
}


/**
 * @brief      Print help message and exit
 *
 * @param      name  Program name (argv[0])
 */
[[noreturn]] void printHelp(const char* name)
{
    cerr << "grommunio database configuration management tool\n"
            "Usage:\n"
         "\t" << name << " set [(-b | --batch)] [(-i | --init)] [(-v | --verbose)] [--] <service> <file> <key> [<value>]\n"
         "\t" << name << " get [(-v | --verbose)] [--] <service> <file> [<key>]\n"
         "\t" << name << " delete [(-v | --verbose)] [--] <service> [<file> [<key>]]\n"
         "\t" << name << " commit [--] service [file]\n"
         "\t" << name << " (-h | --help)\n"
         "\nOptional arguments:\n"
         "\t-b\t--batch\t    Do not autocommit changes\n"
         "\t-h\t--help\t    Print this help and exit\n"
         "\t-i\t--init\t    Only set variable if it does not exist, otherwise exit with error\n"
         "\t-v\t--verbose   Increase verbosity level (max 3)\n"
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
    bool commandsOnly = false;
    for(char** argp = argv+1; *argp != nullptr; ++argp)
    {
        char* arg = *argp;
        if(!commandsOnly && *arg == '-')
        {
            if(*(++arg) == '-')
            {
                ++arg;
                if(!strcmp(arg, "batch"))
                    batch = true;
                else if(!strcmp(arg, "help"))
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
                    case 'b':
                        batch = true; break;
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
    else if(args[Command] == "commit")
    {
        if(nargs < 2)
            return argerr("Too few arguments.");
        if(nargs > 3)
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
    string host = "127.0.0.1", user, passwd, db, port="3306", line;
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
        for_each(key.begin(), key.end(), [](char& c){c=tolower(c);});
        if(key == "mysql_host")
            host = std::move(value);
        else if(key =="mysql_port")
            port = std::move(value);
        else if(key == "mysql_username")
            user = std::move(value);
        else if(key == "mysql_password")
            passwd = std::move(value);
        else if(key == "mysql_dbname")
            db = std::move(value);
    }
    unsigned int iport;
    try
        {iport = stoul(port);}
    catch(const invalid_argument&)
        {return nullptr;}
    if(verbosity == 2)
        cerr << "Config file read.\n";
    if(verbosity >= 3)
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


/**
 * @brief      Amount of bytes needed to store result of `quoteSize`
 *
 * @param      str   String to be quoted
 *
 * @return     Number of bytes needed, including terminating null character
 */
size_t quoteSize(const char* str)
{
    if(!*str)
        return 1;
    size_t len;
    for(len = 3; *str; ++str)
        len += *str == '\''? 5 : 1;
    return len;
}


/**
 * @brief      Write BASH quoted string
 *
 * Encapsulates `from` in single quotes (`'`) and replaces each occurrence of
 * a single quote by the sequence `'"'"'` which is interpreted as a single
 * quote by bash.
 *
 * If the input string has a length of n, the result will take at most 5*n+3
 * bytes of memory (single quotes at start and end plus terminating null
 * character)
 *
 * @param      from  Original string
 * @param      to    Buffer the quoted string is written to
 */
void quoteVar(const char* from, char* to)
{
    if(!*from)
    {
        *to = 0;
        return;
    }
    *(to++) = '\'';
    for(; *from; ++from)
    {
        if(*from == '\'')
        {
            memcpy(to, "'\"'\"'", 5);
            to += 5;
        }
        else
            *(to++) = *from;
    }
    *(to++) = '\'';
    *to = 0;
}

/**
 * @brief      Substitute variables in command string
 *
 * Substitutes each occurence of `$VARNAME` with the content in `vars[VARNAME]`.
 * If `VARNAME` is not in `vars`, it is substituted with the empty string.
 *
 * The content is automatically enclosed by single quotes, and each single quote
 * in the content is replaced by `'"'"'` to make it shell secure.
 *
 * @param      command  Command string
 * @param      vars     Variable name -> content mapping
 *
 * @return     Command string withsubstituted variables
 */
string subVars(const string& command, const unordered_map<string, string>& vars)
{
    string result;
    string var;
    size_t last = 0;
    for(size_t index = command.find('$'); index != string::npos; index = command.find('$', last))
    {
        result.append(command.begin()+last, command.begin()+index);
        ++index;
        if(index == command.length())
            return result+"$";
        if(command[index] == '$')
        {
            result += '$';
            last = index+1;
        }
        else
        {
            for(last = index; last < command.length() && isalnum(command[last]); ++last);
            var.assign(command, index, last-index);
            auto it = vars.find(var);
            if(it != vars.end())
            {
                char quoted[2048];
                quoteVar(it->second.c_str(), quoted);
                result += quoted;
            }
        }
    }
    result.append(command, last);
    return result;
}

/**
 * @brief      Commit configuration changes
 *
 * Searches for an appropriate command in grommunio-dbconf/<service> according
 * to the number of arguments provided.
 *
 * If no command is found,
 *
 * @param      mconn  The mconn
 *
 * @return     Error code or 0 if successful
 */
int commit(mysqlconn_t& mconn)
{
    static const int QLEN = 4096;
    char query[QLEN];
    MYSQL* conn = mconn.get();
    CmdLevel target = hasArg(Key)? CMD_KEY : hasArg(File)? CMD_FILE : CMD_SERVICE;
    if(snprintf(query, QLEN, "SELECT `key`, `value` FROM `configs` "
                "WHERE `service`=\"grommunio-dbconf\" AND `file`=\"%s\" AND `key` LIKE \"commit_%%\"",
                 args[Service].c_str()) >= QLEN)
        return 501;
    if(mysql_query(conn, query))
        return 502;
    mysqlres_t res(mysql_store_result(conn));
    string command;
    int level = -1;
    for(my_ulonglong i = 0; i < mysql_num_rows(res.get()); ++i)
    {
        MYSQL_ROW row = mysql_fetch_row(res.get());
        int temp = cmdLevel(row[0]);
        if(temp > target)
            continue;
        if(temp > level)
        {
            level = temp;
            command = row[1];
        }
        if(temp == target)
            break;
    }
    if(level == -1)
    {
        if(verbosity >= 2)
            cerr << "No applicable commit command found.\n";
        return 0;
    }
    if((level == CMD_KEY && keyCommits.count(command) == 0) |
       (level == CMD_FILE && fileCommits.count(command) == 0) |
       (level == CMD_SERVICE && serviceCommits.count(command) == 0))
    {
        cerr << "Invalid command - commit aborted.\n";
        return 503;
    }
    std::unordered_map<string, string> vars = {{"SERVICE", args[Service]}};
    if(level >= CMD_FILE && command.find("$FILE") != string::npos)
    {
        if(snprintf(query, QLEN, "SELECT `key`, `value` FROM `configs` WHERE `service`=\"%s\" AND `file`=\"%s\"",
                    args[Service].c_str(), args[File].c_str()) >= QLEN)
            return 504;
        if(mysql_query(conn, query))
            return 505;
        res.reset(mysql_store_result(conn));
        string file;
        for(my_ulonglong i = 0; i < mysql_num_rows(res.get()); ++i)
        {
            MYSQL_ROW row = mysql_fetch_row(res.get());
            file += row[0];
            file += "=";
            file += row[1];
            file += "\n";
        }
        vars.emplace("FILE", move(file));
        vars.emplace("FILENAME", args[File]);
    }
    if(level == CMD_KEY)
    {
        vars.emplace("KEY", args[Key]);
        vars.emplace("VALUE", args[Value]);
        vars.emplace("ENTRY", args[Key]+"="+args[Value]);
    }
    command = subVars(command, vars);
    if(verbosity)
        cerr << command << endl;
    int result = system(command.c_str());
    if(result)
    {
        cerr << "Commit failed with exit code " << result << endl;
        return 506;
    }
    return 0;
}


int grommunioConfSet(mysqlconn_t& mconn)
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
    if(!batch)
        return commit(mconn);
    return 0;
}


int grommunioConfGet(mysqlconn_t& conn)
{
    static const int QLEN = 4096;
    char query[QLEN];
    int pos = snprintf(query, QLEN, "SELECT `key`, `value` FROM `configs` WHERE `service`='%s' AND `file`='%s'",
                       args[Service].c_str(), args[File].c_str());
    if(pos >= QLEN)
        return 201;
    if(hasArg(Key) && snprintf(query+pos, QLEN-pos, " AND `key`='%s'", args[Key].c_str()) >= QLEN-pos)
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


int grommunioConfDel(mysqlconn_t& conn)
{
    static const int QLEN = 4096;
    char query[QLEN];
    int pos = snprintf(query, QLEN, "DELETE FROM `configs` WHERE `service`='%s'", args[Service].c_str());
    if(pos >= QLEN)
        return 301;
    if(hasArg(File))
    {
        if((pos += snprintf(query+pos, QLEN-pos, " AND `file`='%s'", args[File].c_str())) >= QLEN)
            return 302;
    }
    if(hasArg(Key))
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
        res = grommunioConfSet(conn);
    else if(args[Command] == "get")
        res =  grommunioConfGet(conn);
    else if(args[Command] == "delete")
        res = grommunioConfDel(conn);
    else if(args[Command] == "commit")
        res = commit(conn);
    if(verbosity)
    {
        if(res)
            cerr << "Error (" << res << ")\n";
        else
            cerr << "Success.\n";
    }
    return res;
}
