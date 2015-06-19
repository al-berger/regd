# regd "1"

## NAME

regd - Registry daemon.

## SYNOPSIS

regd <*COMMAND*> [*ARGUMENTS*]

## DESCRIPTION

__regd__ is a server daemon program for storing or temporarily keeping 
information in the form of name/value pairs (tokens) and returning it 
in response to commands.

__regd__ can run either as a network server on a dedicated IP address
or as a local server using a local file ("Unix file socket") as a server
address.

Once __regd__ server is started it remain running and responds to commands
which are sent to it. Commands manage the server behaviour and are used 
for adding information to the storage, retrieving or deleting it, 
restarting and stopping the server, etc.

Commands can be sent to the running __regd__ server in one of two ways: 
via command line with another __regd__ instance invoked as a client, or
via sockets, if the connection to __regd__ server is made from another
or program.

Each user can have a separate regd server running, containig her own 
information. If needed, one user can have several regd server instances
running with different server names. Each server instance has its own
persistent and temporary storage.

Each regd server running on a file socket can have one of three permission 
access level for all its data: _private_, _public-read_ or _public_.

### Starting regd server  

When __regd__ server is started (invoked with the __--start__ option), 
it must be provided with four configuration options (all of them have 
default values): server address, access level, server name and data file.

_Server address_  

The server address through which it can be contacted from other process. 

If __regd__ is started on an IP address,  the address must be specified with
__--host__ and __--port__ command line options (see below). 

If __regd__ is started on a file socket (which is the default option), its 
address is a server name.  

_Server name_  

If one user have more than one _regd_ server running on _file sockets_, they need
to be distinguished via different server instances names. The server name is
assigned to a _regd_ server instance on startup with __--server-name__ command
line option. The server name can have length up to 32 characters. Names must be 
unique within one user account. Different users can have identically named _regd_
servers.

If a user has only one _regd_ server instance running on a file socket, then this
server may or may not be provided with a name. _regd_ servers running on IP
addresses don't have names and __--server-name__ option is ignored on their startup.  

_Access level_  

A _regd_ server running on a UNIX file socket has a permission level for accessing 
and manipulating its data. A single permission level applies to all the data kept 
in session and persistent tokens on the server. Secure tokens remain private at all 
permission levels. Permission level is set on server startup with __--access__ 
option and can be one of three values:
- private : Only user who started the server instance (server process owner) can send 
commands to the server. All commands from other users are denied. This is the default 
level.
- public-read : The data on the server except of secure tokens is "world-readable". 
The server process owner have full access to the server. From other users the following 
commands are executed: __--check__, __--list-all__, __--list-pers__, __--list-sessions__, 
__--get__, __--get-pers__. All other commands from other users are denied.
- public : The data on the server except of secure tokens is "world-readable" and 
"world-writable". All users having access to the machine's filesystem can read, add,
modify and remove session and persistent tokens (secure tokens are not accesible to
users other than the server process owner). 

If __--access__ option is not present at server startup, then the server permission level 
is set as 'private' by default.

The following commands can be executed only by the server process owner at all permission
levels: __--start__, __--stop__, __--restart__, __--get-sec__, __--load-file-sec__, 
__--remove-sec__, __--remove-section-sec__, __--clear-sec__.

_Data file_  

Each server instance by default has its own persistent storage: data file from which
persistent tokens are read startup and to which they are saved back if new tokens are
added, or existing tokens are modified or removed. The default name of the data file is
automatically composed out of three parts:

1. Directory: the _regd_ data directory: the default one or which is defined in _regd.conf_. 
2. File: the server name for servers on file sockets or "$host.$port" for servers on IP
addresses.
3. Extension: ".data" file extension



### Communicating with regd server  

Running _regd_ server keep listening for incoming commands on the address on
which it has been started (file socket or IP address). It can be contacted only
through this address. The socket/IP address can be used directly by other programs
to send commands to _regd_. Also _regd_ itself can be used in the client mode
to send commands to _regd_.

To send a command to a _regd_ server, _regd_ in the client mode is invoked with
following general syntax (items in square brackets are optional):

__regd__ [<_--host_> <_--port_> | <_--server-name_>] [_log-level_] _command_

A server running on an IP address always must be contacted with the __--host__
and __--port__ present on the command line:

$ regd --host some.hostname --port NNNN --get "someItem"

A server running on a UNIX file socket must be contacted through it's server name
(if it was started with a __--server-name__ option) and with the username of the
server process owner if the server was started by a user other than the user 
sending it a command. User name is prefixed to the server name with '@' symbol:  

alice@servername

If the server was started without server name, then only the user name with '@' must be
used as the server address. For example, if a server was started by user 'alice' without
the server name, as follows:

$ regd --start --access public-read

then user 'alice' can contact the server as follows:

$ regd --add someItem=someValue

User 'bob' can contact this server as follows:

$ regd --server-name alice@ --get someItem

If the server was started by user 'alice' with the name 'info':

$ regd -- start --server-name info --access public-read

then user 'alice' can contact the server as follows:

$ regd --server-name info --add someItem=someInfo

and user 'bob' can contact the server as follows:

$ regd --server-name alice@info --get someItem

### Tokens

In __regd__ documentation the term _token_ designates the basic unit
of information storage. A token consists of a token identifier (_name_)
and data (_value_), which is associated with this name. Both name and 
value are Unicode strings and can hold arbitrary Unicode values of 
arbitrary length. (However, see the NOTES section below about
special cases when a token contains '=', '\' or ':' characters.) 
The token name is used as as the token identifier.

Tokens are grouped in sections. Token name can contain an 
optional section name, which is the part of the name up to the
first colon. E.g.: 
"SECTION NAME : token name". 
If the section name is not present in the token name, the token
is stored in the section named 'general'. If the section name contains
colons within itself, they must be prepended with backslashes.

A token can be one of two types regarding its lifetime:
_session_ token or _persistent_ token. Session tokens 
exist in the registry from the moment of their addition
until the program's exit or until their removal with a command.
Persistent tokens are stored in a disk file, automatically 
loaded in the registry on each program start and exist until
they are explicitly removed with a removal command.

### Secure tokens

Secure tokens are the tokens that are loaded with secure loading command:
__--load-file-sec__. This command by default is meant to call an encryption
program, which reads an encrypted file with secure tokens, prompting the
user for the password if needed, and the pipes the file text to the __regd__ 
through a shell pipe. But user can use any other command of loading secure
tokens as long as it returns the list of "name=value" pairs.

Secure tokens are always session tokens: they are never stored on disk and 
they are discarded from the RAM when the server is stopped or when they
are removed with a removing command. Also secure tokens are not 
included in the print output of listing commands.


## COMMANDS

### Help and version  

### --help
Display short command summary.

### --version
Display the program version.

### Starting, stopping, checking a server  

### --start
Start __regd__. This command can be used with command line options: __--host__, __--port__, __--user__, __--log-level__ (see below). To start __regd__ on an Internet address, the command line options __--host__ and __--port__ must contain the host name and port number of that address. If "--host" and "--port" are not specified, __regd__ will run on a Unix file socket as a local daemon.

### --stop
Stop __regd__. All session tokens are discarded.

### --restart
Restart __regd__. All session tokens are discarded.

### --check
Check if the __regd__ is running.

### Adding tokens to the server  

### --add <_name=value_>
Add a session token. If a token with such name already exists, the token value is not updated.

### --set <_name=value_>
Add a session token. If a token with such name already exists, the token value is updated.

### --add-pers <_name=value_>
Same as __--add__, but the token is added to the persistent tokens.

### --set-pers <_name=value_>
Same as __--set__, but the token is added to the persistent tokens.

### --load <_name1=value1_>[<token_separator>_name2=value2_...]  
Add multiple session tokens. Each name/value pair must be separated from the previous one with the token separator. The default token separator is a three-character sequence: _@#$_ . With this default separator multiple tokens are specified like this:  
"name1=value1@#$name2=value2"  
The value of the token separator can be customized in _regd.conf_ file. 

### --load-pers <_name1=value1_>[<token_separator>_name2=value2_...]
Same as __--load__, but adds persistent tokens, rather
than session ones.

### --load-file <_filename_>
Add session tokens from a file. _filename_ - the path
of the file with tokens. The file must contain "name=value"
pairs with one pair per line.

### --load-file-pers <_filename_>
Same as __--load-file__, but adds persistent tokens, rather
than session ones.

### --load-file-sec [_filename_]
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
('--get-sec') is received, a _pinentry_ dialog window is 
shown to the user, prompting for entering the password. 
If the password is correct, _gpg_ program then reads the 
contents of the encrypted file and pipes the file text to 
the __regd__, where it's kept in RAM. 
With this procedure the decrypted file contents are never written 
toa disk and always remain in RAM.

The command for reading encrypted files can be changed and
specified in the _regd.conf_.

### Getting tokens from the server  

### --get <_name_>
Get the value of a session token.

### --get-pers <_name_>
Get the value of a persistent token.

### --get-sec <_name_>
Get the value of a secure token.

### Removing tokens from the server  

### --remove <_name_>
Remove a session token 

### --remove-pers <_name_>
Remove a persistent token 

### --remove-sec <_name_>
Remove a secure token.

### --remove-section <_section_>
Remove a section in session tokens.

### --remove-section-pers <_section_>
Remove a section in persistent tokens.

### --remove-section-sec <_section_>
Remove a section in secure tokens.

### --clear-session
Remove all session and secure tokens.

### --clear-sec
Remove all secure tokens.

### Listing tokens  

### --list-all
Print all the session tokens and persistent tokens. (Secure tokens are not listed.)

### --list-session [_section1_[ _section2_...]]
Print the specified sections of session tokens or all sections if sections are not specified.

### --list-pers [_section1_[ _section2_...]]
Print the specified sections of persistent tokens or all sections if sections are not specified.


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
The pathname of the file from which the server instance will read persistent tokens
and to which they will be stored. 

     
## CONFIGURATION FILE

The configuration file _regd.conf_ is read on the program 
startup. Options in _regd.conf_ residing in _/etc/regd/_ 
are system-wide ( applied for all users using regd ). The
system-wide options can be overriden in a user-level 
_regd.conf_ residing in _~/.config/regd/_ .

Options that can be set in _regd.conf_ are described in
_/etc/regd/conf.regd_ file.

## NOTES

If a token contains any of three characters: '\', ':' or '=',
these cases need special handling: prepending these characters with
backslashes ('\') before using in a command.

1) If the section contain ':' characters, each of these characters must be 
prepended with '\' (backslash) character.

2) If the name contain '=' characters, these characters
must be prepended with '\' characters.

3) If a token (the section or name or value ) contain backslashes, they 
must be prepended with another backslash. 

E.g., if a token has a section "S:S\S=", name "n:n\n=" and value "v:v\v=", 
then in a command string, where tokens have the form "section : name = value",
such a token must be modified as follows:

regd --add "S\:S\\S= : n:n\\n\= = v:v\\v="

That is, in sections two special characters must be backslashed: ':' and '\', 
in names '=' and '\' must be backslashed, and in values only '\' must
be backslashed. The section is separated from the name with
the first unbackslashed ":" and the name is separated from the value with the
first unbackslashed "=".



## AUTHOR

Albert Berger <alberger@gmail.com>