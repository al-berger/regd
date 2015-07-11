# regd "1"

## NAME

regd - Registry daemon.

## SYNOPSIS

regd <*COMMAND*> [*ARGUMENTS*]

## DESCRIPTION

__regd__ is a server daemon program for storing or temporarily keeping 
information in the form of name/value pairs (tokens) and returning it 
in response to commands.

__regd__ can run either as a network server on a dedicated HOST:PORT address
or as a local server using a local file ("Unix file socket") as a server
address.

Once __regd__ server is started it remains running and responds to commands
which are sent to it. Commands manage the server behaviour and are used 
for adding information to the server storage, retrieving or deleting it, 
restarting and stopping the server, getting reports or server variable values, 
etc. When not executing a user command __regd__ server remains in idle state
and consumes almost no resources. 

Commands can be sent to the running __regd__ server in one of two ways: 
via command line using __regd__ as a client, or via sockets. Both these ways
can be used for connecting to __regd__ both manually and programmatically.

Any user on a system can have her own __regd__ server running, containing 
her own information. If needed, one user can have several __regd__ server 
instances running with different server names and different sets of information. 
Each server instance has its own persistent and temporary storage and its
own permission access level.

Each regd server running on a file socket can have one of three permission 
access levels for all its data: _private_, _public-read_ or _public_.

### File socket servers and Internet socket servers  

__regd__ server can be started either on a file ("UNIX domain socket") or
on an Internet socket with an assigned IP address and port number. Any user on
a system can have multiple __regd__ servers of both types simultaneously 
running each with its own data storage. The main differences between file socket
servers and Internet socket servers are the following:

- File socket server runs using a usual filesystem file as its address and can 
only be accessed by users who have access to the filesystem where the file socket is
located. Whereas Internet socket servers can be accessed from any computer, from
which the network address of the __regd__ server can be reached.

- File socket servers have access permission system which allows to restrict access
to data only to certain users accounts, and can be used for safely sharing private 
data only between trusted users. Internet socket servers can only restrict data 
access to certain IP addresses from which they accept commands.

### Regd communication protocol

__regd__ server is started, stopped and communicated with using the __regd__ communication protocol. According to this protocol, all client-server interactions
are done in four steps:

1. Client sends a _query_message_ to Server.
1.1. Server receives the _query_message_.
2. Server sends a _result_message_ to Client.
2.2. Client receives the _result_message_.

All _query_messages_ consists of one required part: _command_ , and one optional 
part: _options_. The _command_ part must contain exactly one command name, which can
be sufficient for parameterless commands (e.g. __check__), and also can include 
either the required parameters (e.g. __get__ command) or optional parameters for commands with default parameter values (e.g. __load-file-sec__). The general __regd__ _query_message_ syntax is 
the following:

regd <_COMMAND_NAME_> [_COMMAND_PARAMETERS_] [_OPTION_NAME_ [_OPTION_PARAMETERS_]]...

Regd command and option names are distinguished by a different naming style. Option
names have '--' or '-' prefixes (for long or short name versions accordingly); e.g.: __--pers__. Command names don't have those prefixes: __add__, __show-log__.

_Result_messages_ have the following general syntax:

<_1|0_CODE_>[_QUERY_RESULT_]

The 1|0 code is either '1' or '0' digit which is always the first symbol in the 
_result_message_. The '1' means that the query was completed successfully, and '0' 
means, that the query failed and the rest of the message is the failure report.

### Starting regd server  
  
When __regd__ server is started, it must be provided with four configuration options (all of them have default values): _server address_, _server name_, _access level_ and _data file_.

_Server_address_  

The server address is the identifying information with which the server can be contacted from another process (or from command line). 

If __regd__ is started on an IP address,  the address must be specified with
__--host__ and __--port__ options (see below). 

If __regd__ is started on a file socket (which is default), its address is the 
name, specified in the __--server-name__ option (or the default name if the server
name wasn't sepecified). If a file socket server is contacted from another
user account, the server name must be prepended with the user name of the server process owner (the name of the account from which the server was started) and '@' character. E.g.: username@servername.

_Server_name_  

If one user has more than one __regd__ server running on _file_sockets_, these 
servers need to be distinguished between each other via different server names. The server name is assigned to a _regd_ server instance on startup with __--server-name__ 
option. The server name can have the length up to 32 characters. Names 
must be unique within one user account. Different users can have identically 
named _regd_ servers.

If a user has only one __regd__ server running on a file socket, then this
server may or may not be provided with a name (if no name is provided on startup,
the default name is used and the server can be communicated without specifying its name). 

__regd__ servers running on IP addresses don't have names (additional to the 'host:port' address) and __--server-name__ option is ignored on their startup.  

_Access_level_  

A __regd__ server running on a UNIX file socket has the permission level for accessing 
and manipulating its data. Currently a single permission level applies to all the data kept in session and persistent tokens on the server. The __regd__ permission control 
distinguishes two groups of users: _private_ and _public_. The _private_ group includes
the user who started the server ("server process owner") and users listed in the
__trusted_users__ option in _regd.conf_ file ("trusted users"). The _public_ group 
includes all other users. 

The server's access permission level is set on server startup with __--access__ option and can be one of three values:  

- __private__ : Only the server process owner and trusted users can send commands to the 
server. All commands from other users are denied. This is the default level.  

- __public-read__ : The data on the server except of secure tokens is "world-readable". 
The server process owner and trusted users have full access to the server. From other 
users the following commands are executed: __get__, __ls__, __check__. All other commands from other users are denied.  

- __public__ : The data on the server except of secure tokens is "world-readable" and 
"world-writable". All users having access to the machine's filesystem can read, add,
modify and remove session and persistent tokens (secure tokens remain private and
can be accessed only by the server process owner and trusted users). 

If __--access__ option is not specified at server startup, the server permission level is set as 'private' by default.

The following commands can be executed only by the server process owner and trusted users at all permission levels ("private commands"): __start__, __stop__, __restart__, 
__add-sec__, __get-sec__, __load-file-sec__, __remove-sec__, __remove-section-sec__, 
__clear-sec__, __report-stat__, __show-log__.

_Data_file_  

Each server instance by default has its own persistent storage: the file from which the 
persistent tokens are read on startup and to which they are saved back when new tokens are added, or existing tokens are modified or removed. The data file name can be provided
with __--datafile__ command line option on server startup. The default name of the data file is used if __--datafile__ option is not present on startup and automatically composed out of three parts:

1. Directory: the __regd__ _data directory_ defined in __'datadir'__ option in _regd.conf_, or the default one ({$HOME/.config/regd/data}) if 'datadir' is not defined . 
2. File: for file socket servers the server name is used as a data file name; for servers on IP addresses the combination of host name and port number is used.
3. Extension: ".data" file extension

The presistent storage can be disabled for a server by specifying "None" in the 
__--datafile__ option on server startup. In this case the server will only work with 
session tokens and commands relating to persistent tokens will be denied.

### Communicating with regd server  

A running __regd__ server keeps listening for incoming commands on the address on
which it has been started (file socket or IP address). The communication with a server
can be done either using the socket/IP address directly from other programs or using __regd__ in client mode to send a command to a __regd__ server.

To send a command to a __regd__ server, __regd__ in the client mode is invoked with
following general syntax (items in square brackets are optional):

<command> [_--host_ _--port_ | _--server-name_] [_--log-level_]  

A server running on an IP address must always be contacted with the __--host__
and __--port__ specified on the command line:

$ regd get "someData" --host some.hostname --port NNNN

A server running on a UNIX file socket must be contacted through it's server name
(if the server was started with a __--server-name__ option) and with the username of the
server process owner if the server was started by a user other than the user 
sending it a command. User name is prefixed to the server name with '@' symbol:  

alice@servername

If the server was started without a server name, then only the username with '@' must be
used as the server address. For example, if a server was started by user 'alice' without
the server name, as follows:

$ regd start --access public-read

then user 'alice' can contact the server as follows:

$ regd add someItem=someValue

User 'bob' can contact that server as follows:

$ regd get someItem --server-name alice@

If the server was started by user 'alice' with the name 'info':

$ regd start --server-name info --access public-read

then user 'alice' can contact the server as follows:

$ regd add someItem=someInfo --server-name info

and user 'bob' can contact the server as follows:

$ regd get someItem --server-name alice@info 

### Tokens

In __regd__ documentation the term _token_ designates the basic unit
of information storage. A token consists of a token identifier (_name_)
and data (_value_), which is associated with this name. Both name and 
value are Unicode strings and can hold arbitrary Unicode values of 
arbitrary length. (However, see the NOTES section below about
special cases when a token contains '=', '\' or '/' characters.) 
The token name is used as the token identifier.

Tokens are grouped in sections. Sections have their own names and can 
contain other sections. Overall the tokens and sections organization structure 
resembles the hierarchical structure of files and directories with naming
convention being similar to the Unix file and directory naming rules.

Each token is stored at a unique address which consists of the "section path"
and the token name:

`section1/section2/tokenName1`

To store a token in a certain section, the section name (and the names of all 
containing sections - "section path") must be specified along with the token name 
when the token is added to a server:

`regd add "section1/section2/tokenName1 = tokenValue1"

If the section path is not specified when a token is added, the token is stored
in the default section and can be accessed without a section name.

To access the token value, the fully qualified name token name (the section path
and the token name) must always be used:

`regd get "section1/section2/tokenName1"`

(Note the absence of '/' character in the beginning of the section path.)
The fully qualified name includes one more component: the token storage type.

A token can be one of two types regarding its lifetime:
_session_ token or _persistent_ token. Session tokens 
exist in the server storage from the moment of their addition
until the program's exit or until their removal.
Persistent tokens are automatically stored in a disk file, automatically 
loaded to the registry on each program start and exist until
they are explicitly removed with a removal command.

When a token is added to a server, it is added by default as a session token. 
To add a token as a persistent token, the __--pers__ option should additionally 
be specified:

`regd get "section1/section2/tokenName1" --pers`

So one can have two tokens on one server with identical section paths and names,
but with different storage types. When adding or accessing session tokens, only their
section path and name must be specified. When adding or accessing persistent tokens,
the __--pers__ flag must be added to the query options.


### Secure tokens

Secure tokens are tokens that have certain access restrictions and security
enhancements in their handling:

- in file socket servers they are never shared to public and remain private (
accessible only by the server owner and trusted users) even in servers with
'public' and 'public-read' access.

- they always have session lifetime and never stored to disk and they are discarded 
from the RAM when the server is stopped or when they are removed with a removal 
command. Also secure tokens are not included in the print output of listing commands.

- they can automatically be loaded from an encrypted file or from other secure
source. with secure loading command: __--load-file-sec__ . This command by default 
is meant to call 'gpg' encryption program, which reads an encrypted file with secure 
tokens, prompting the user for the password if needed, and then pipes the file text 
to __regd__ through a shell pipe. A user can use any other command of loading 
secure tokens as long as it returns the list of "name=value" pairs through a shell
pipe.


## COMMANDS

### Help and version  

### help
Display short command summary.

### version
Display the program version. Without __--server-side__ option the client's version is
displayed. With --server-side option - the server's regd version is displayed.

### Starting, stopping, checking a server  

### start
Start __regd__. This command can be used with options: __--host__, __--port__, __--server-name__, __--access__, __--datafile__, __--log-level__ (see below). To start __regd__ on an Internet address, the command line options __--host__ and __--port__ must contain the host name and port number of that address. If "--host" and "--port" are not specified, __regd__ will run on a Unix file socket as a local daemon.

### stop
Stop __regd__. All session tokens are discarded.

### restart
Restart __regd__. All session tokens are discarded.

### check
Output the uptime of the running __--regd__ server.

### Adding tokens to the server  

### add <TOKEN1>[ TOKEN2]... [--pers][--force|-f]
Add a token to server. Without __--pers__ option the token is added as a session token. With --pers option the token is added as a persistent token. If a token with such storage type, section path and name already exists, the option __--force__ causes the existing token's value to be replaced with the new value. If the token contains whitespace characters, it must be included in quotes. Multiple space separated tokens can be specified in the command parameter.

### load-file <_filename_>
Add tokens to server from a text file. _filename_ - the path of the file with tokens. 
The file must contain tokens as <name = value> pairs grouped under section paths in square brackets:

[section1/section2]
name1 = value1
name2 = value2

[section1/section3]
name3 = value3
name4 = value4

Section names, when not at the first line of the file, must be preceded by an empty line. Square brackets surrounding the section name must be the first and the last character on the line. Section names can include the same characters as tokens (any character except of null character, slash ('/') and cannot consists of a single dot).

A single token can span several lines, in which case all lines beginning from the second one must start with either a single tab or with a single space character (all tabs and spaces beyond the first one are considered a part of the token). 

All tokens in the file are added to a single storage type: as session tokens by default, or as persistent tokens if the __--pers__ option is specified.

### load-file-sec [_filename_]
Add secure tokens from an encrypted file. _filename_ - the 
path of the file with secure tokens. _filename_ can be
ommited, in which case the default encrypted file will be 
read. The default name of the default file is:
_~/.sec/safestor.gpg_ 
The name of the default encrypted file can be specified in
_regd.conf_.
The default command for reading encrypted files is:  

"gpg --textmode -d FILENAME"  

For this default command could be used, _gpg_, _gpg-agent_ 
and _pinentry_ programs needs to be installed and run on the 
computer. With this command, when the first command during a
program session for getting a value of a secure token 
('get-sec') is received, a _pinentry_ dialog window is 
shown to the user, prompting for entering the password. 
If the entered password is correct, _gpg_ program then reads the 
contents of the encrypted file and pipes the file text to 
the __regd__, where it's kept in RAM. 
With this procedure the decrypted file contents are never written 
to a disk and always remain in RAM.

The command for reading encrypted files can be changed and
specified in _regd.conf_.

### Getting tokens from the server  

### get <_TOKENPATH_>
Get the value of a session token. Token path must consist of section path and token 
name. For persistent tokens __--pers__ option must be specified in the query.

### get-sec <_name_>
Get the value of a secure token.

### Removing tokens from the server  

### remove <_name_>
Remove a token 

### remove-sec <_name_>
Remove a secure token.

### remove-section <_section_>
Remove a section.

### --remove-section-sec <_section_>
Remove a section in secure tokens.

### --clear-session
Remove all session and secure tokens.

### --clear-sec
Remove all secure tokens.

### Listing tokens  

### ls [_SECTION_] [_--pers_] [_--tree_] [_--novals_]
Print all the session tokens and persistent tokens. (Secure tokens are not listed.)

### --list-session [_section1_[ _section2_...]]
Print the specified sections of session tokens or all sections if sections are not specified.

### --list-pers [_section1_[ _section2_...]]
Print the specified sections of persistent tokens or all sections if sections are not specified.

### Information commands

### --report-stat
Display some statistics about this server.

### --show-log <N>
Display the last N lines of the _regd_ log file if the log file is specified in _regd.conf_.


## COMMAND LINE OPTIONS
All _regd_ command line options can be used both when starting a server as well as when
invoking regd as a client (for sending commands to the running server).

### --log-level <_log_level_>
This command line start option sets the level of the log
output. Log level can be one of the following values:
DEBUG, INFO, WARNING, ERROR, CRITICAL.
Log level is the type of events which which cause the
program to produce output. Can be used 

### --server-name <_server_name_>
This option applies only to file socket servers. For servers running on an IP address
it is ignored. 
_Server mode_ : When starting a server on a file socket, this option assigns server the name 
which will be used for sending it commands and distinguishing it from other servers of the 
same user. When starting the first file socket server instance, the server name is optional 
(if it is omitted, the default name is used). When starting second and following instances, the 
server name is mandatory.  
The server name must be unique within one user account. Different users on one machine
can have identically named servers.  
The server name can have length up to 32 characters.  
_Client mode_ : When contacting to a running server, the server name must be specified on the
command line in following cases:
- the server command is sent from a guest user (that is from a user account other than the 
server process owner account). In this case the server name must be prefixed with the server 
process owner username and '@' character.
- the server was explicitly assigned a name on startup. In this case the server owner must 
contact the server using the assigned server name. Guest users must use the prefixed server 
name, described in the previous section.  

If a server was started without server name, the guest users must use just the username of the
server owner with '@' appended as the server name.
Examples:  

# User alice starts two servers: one with the default name 
# and one with a custom name

$ regd --start --access public-read
$ regd --start --server-name info --access public-read

# User alice contacts both servers: without the server 
# name specified, the default name is used

$ regd --add "item1=value1"
$ regd --server-name info --add "item2=value2"

# User bob contacts these servers:

$ regd --server-name alice@ --get item1
$ regd --server-name alice@info --get item2

### --host
This option applies only to servers running on IP addresses.  
When starting a server on an IP address, this option specifies the name of the host to 
which the server must be bound:  

regd --start --host some.hostname --port NNNN

In client mode this option specifies the name of the host where the
server to which the command must be sent is running:  

regd --host some.host --port NNNN --get "someInfo"

### --port
This option applies only to servers running on IP addresses.  
When starting a server on an IP address, this option specifies the port number on 
which the server must be listening.  

In client mode this option specifies the port where the server to which the command 
must be sent is listening.  

### --datafile
The full pathname of the file from which the server instance will read persistent tokens
and to which they will be stored. If this option is not present in command line, the server
is started using the default file name in the directory specified in _datadir_ option in
_regd.conf_. If _--datafile_ option has the value _None_, then persistent tokens will not
be supported by the server instance: all commands relating to persistent tokens will fail.

### --auto-start  
If this option is present, then before executing the command, __regd__ will check if the
server is running at the specified address, and will try to start it if it's not running.

## CONFIGURATION FILE

The configuration file _regd.conf_ is read on the program 
startup. Options in _regd.conf_ residing in _/etc/regd/_ 
are system-wide ( applied for all users using __regd__ ). The
system-wide options can be overriden in a user-level 
_regd.conf_ located in _~/.config/regd/_ directory.

Options that can be set in _regd.conf_ are described in
_/etc/regd/conf.regd_ file.

## NOTES

If a token contains any of the following three characters: '\', ':' or '=',
then certain rules must be observed because colon in _regd_ is used as the
section name separator, equals sign is used as the name/value separator and
backslash is a special system character.

1) If the section contains ':' characters, each of these characters must be 
prepended with '\' (backslash) character (prepending a character with backslash
is called 'escaping' character).

2) If the name contains '=' characters, each of these characters
must be escaped.

3) If a token (the section or name or value ) contain backslashes, they 
must be prepended with another backslash.

4) If the section or name ends with backslash, then the separator (colon or equals
sign) that follows after it, must be prepended with space.

E.g., if a token has a section "C:\", name "TEMP\a=b.txt" and value "D:\temp\a=b.txt", 
then when adding this token to _regd_ in the "section:name=value" form,
it must be modified as follows:

regd --add "C\:\\ :TEMP\\a\=b.txt = D:\\temp\\a=b.txt"

That is, colons must be escaped only in sections, equals signs must be escaped only in
names, and backslashes must be escaped everywhere. And if a section or name ends with
backslash, it must be followed by space.



## AUTHOR

Albert Berger <alberger@gmail.com>