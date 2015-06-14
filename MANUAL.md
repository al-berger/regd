# regd "1"

## NAME

regd - Registry daemon.

## SYNOPSIS

regd <*COMMAND*> [*ARGUMENTS*]

## DESCRIPTION

Stores information in the form of name/value pairs (tokens) 
and returns it in response to commands.

Token (name and value) is a pair of arbitrary Unicode strings
separated by '=' character. Name string therefore cannot 
contain '=' character.

The value string is retrieved with a command using the name 
string as the token identificator.

Tokens are grouped in sections. Token name can contain an 
optional section name, which is the part of the name up to the
first colon. E.g.: 
"SECTION NAME : token name". 
If the section name is not present in the token name, the token
is stored in the section named 'general'.

A token can be one of two types regarding its lifetime:
_session_ token or _persistent_ token. Session tokens 
exist in the registry from the moment of their addition
to the program exit or until their removal with a command.
Persistent tokens are stored in a disk file, automatically 
loaded in the registry on each program start and exist until
they are explicitly removed with a removal command.

From encrypted files secure tokens can be loaded. Secure tokens
are always session tokens (they are never stored on disk).
Also secure tokens are not included in the print output of 
listing commands.


## COMMANDS

### __--start__
Start regd. This command can be used with a command line option '__--log-level__' (see below).

### --stop
Stop regd.

### --restart
Restart regd.

### --check
Check if the regd is running.

### --add <_name=value_>
Add a session token. If a token with such name already exists, the token value is not updated.

### --set <_name=value_>
Add a session token. If a token with such name already exists, the token value is updated.

### --add-pers <_name=value_>
Same as __--add__, but the token is added to the persistent tokens.

### --set-pers <_name=value_>
Same as __--set__, but the token is added to the persistent tokens.

### --get <_name_>
Get the value of a session token.

### --get-pers <_name_>
Get the value of a persistent token.

### --get-sec <_name_>
Get the value of a secure token.

### --list-all
Print all the session tokens and persistent tokens. (Secure tokens are not listed.)

### --list-session [_section1_[ _section2_...]]
Print the specified sections of session tokens or all sections if sections are not specified.

### --list-pers [_section1_[ _section2_...]]
Print the specified sections of persistent tokens or all sections if sections are not specified.

### --load <_name1=value1_>[<token_separator>_name2=value2_...]  
Add multiple session tokens. Each name/value pair needs to be separated from the previous one with the token separator. The default token separator is a three-character sequence: _@#$_ . With the default separator multiple tokens are specified like this:
"name1=value1@#$name2=value2"
The value of the token separator can be customized in _regd.conf_ file. 

### --load-pers <_name1=value1_>[<token_separator>_name2=value2_...]
Same as __--load__, but adds persistent tokens, rather
than session ones.

### --load-file <_filename_>
Add session tokens from the file. _filename_ - the path
of the file with tokens.

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
computer. With this command, when the first query during a
program session for getting a value of a secure token 
('--get-sec') is received, a _pinentry_ dialog window is 
shown to the user for receiving the password. 
If the password is correct, _gpg_ program then reads the 
contents of the encrypted file and pipes the file text to 
the _regd_, where it's stored in RAM. 
With this procedure decrypted contents are never written to
a disk and always remain in RAM.

The command for reading encrypted files can be changed and
specified in the _regd.conf_.


## COMMAND LINE START OPTIONS

### --log-level <_log_level_>
This command line start option sets the level of the log
output. Log level can be one of the following values:
DEBUG, INFO, WARNING, ERROR, CRITICAL.
Log level is the type of events which which cause the
program to produce output.

     
## CONFIGURATION FILE

The configuration file _regd.conf_ is read on the program 
startup. Options in _regd.conf_ residing in _/etc/regd/_ 
are system-wide ( applied for all users using regd ). The
system-wide options can be overriden with user-level 
_regd.conf_ residing in _~/.config/regd/_.

Options that can be set in _regd.conf_ are described in
_/etc/regd/conf.regd_ file.

## AUTHOR

Albert Berger <nbdspcl@gmail.com>






