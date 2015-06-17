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

### Invoking regd  

When __regd__ server is started (invoked with the __--start__ option), 
it must be provided with the address through which it will be communicating. 

If __regd__ is started on an IP address, additional command line options
must include __--host__ and __--port__. 

If __regd__ is started on a file socket (which is the default option),
it may be provided through the __--user__ command line option with a valid 
system user name for specifying the server address: the socket file is
created in the _/var/run/user/$USERID/_ directory, to which the invoking
user must have write access. If the user name is not specified with __--user__
option, the file socket is created using the current user ID.

On a system several __regd__ server instances can simultaneously run (each keeping
information for a separate user). If a user A wants to send a command to 

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

### 

## COMMANDS

### Starting, stopping server  

### __--start__
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


## COMMAND LINE RUN OPTIONS
All command line run option can be used both when starting a server as well as when invoking
regd as a client (for sending commands to the running server).

### --log-level <_log_level_>
This command line start option sets the level of the log
output. Log level can be one of the following values:
DEBUG, INFO, WARNING, ERROR, CRITICAL.
Log level is the type of events which which cause the
program to produce output.

### --user <_username_>
The user name of the effective owner of the server process
which the command is sent to.

### --host
In a starting server command this option specifies the name of the host to which
the server must be bound:  

regd --start --host some.hostname --port ####

In an invoking client command this option specifies the name of the host where the
server is running:  

regd --host some.host --port NNNN --get "someInfo"

### --port
In a starting server command this option specifies the port number on which
the server must be listening.

In an invoking client command this option specifies the port number where the
server is listening.

     
## CONFIGURATION FILE

The configuration file _regd.conf_ is read on the program 
startup. Options in _regd.conf_ residing in _/etc/regd/_ 
are system-wide ( applied for all users using regd ). The
system-wide options can be overriden with user-level 
_regd.conf_ residing in _~/.config/regd/_.

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

Albert Berger <nbdspcl@gmail.com>






