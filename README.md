  regd
=========

__regd__ is a data storage service program (like Windows registry) where other 
programs and computer users can keep and retrieve back various data such
as configuration settings, dynamic data, etc. The data is organised and stored in hierarchical structure which resembles computer's filesystem structure:

`/ses/someProgram/varName1 = value1`

__regd__ can be used both by human users and by scripts or programs via 
__command_line__ or through __sockets__.

__regd__ can securely handle confidential data. A user can load to
regd an encrypted file with confidential data (e.g. database 
password) and regd will function as a keyring-agent or password
manager, keeping this data in RAM until the user clears it out.

On a system several users can have their own regd server instances and one
user can have several __regd__ server instances with different data and access
permissions.

Access to data on __regd__ server can be restricted with access level permissions. 
All data on a __regd__ server can be _private_, _public-readable_, or _public_.

__regd__ can keep data temporarily or it can permanently store data on disk 
and load it automatically during startup.

Use cases of __regd__ include:  

- interprocess communication: using __regd__ as memory for data shared between several programs (_"shared_memory"_)

- centralized persistent storage of programs' configuration settings, data, etc.
With regd scripts and programs can persistently store and retrieve any specific setting with just one command. E.g. in a bash script this can look as follows:

`confSetting="$(regd get "someScript/someSetting" --pers)"`  
`someData="abcde"`  
`regd --set-pers "someScript: someData = ${someData}"`

- password agent (or more generally - "secure data cache") for providing other programs 
and scripts with data which was read from encrypted file (or loaded with some other 
secure method), is always kept in RAM and is never stored in files in unencrypted form.

- temporary data cache for a single program;

- centralized settings or data exchange server running on an IP address in a network,
where other machines in the network can store and retrieve data in the same way
as for the local usage. __regd__ can be configured for allowing access to data only to
certain IP addresses.

__regd__ manual can be found [here](https://github.com/nbdsp/regd/blob/master/data/MANUAL.md)

## Examples of using regd

From command line (all __regd__ output always begins either with '1' - if the command was completed successfully, or with '0' - otherwise. This is necessary for distinguishing successfully returned stored data from error messages. ):

```
$ regd start
$ regd add "some variable = some value"
1
$ regd get "some variable"
1some value
$ regd add "SOME APP: some setting = 1234" --pers
1
$ regd ls
1
[global]
    some variable = some value
[SOME APP]
    some setting = 1234
$ regd check
1Ready and waiting.
$ regd stop
```

From programs via sockets:

```
# Python 

def regdcmd(cmd, data):
	# This function connects to the regd socket, sends it the command 
	# and receives the response.

var1 = regdcmd( cmd="get", data="SOME APP: some setting" )
var2 = regdcmd( cmd="get", data="ANOTHER APP: some data" )

var3 = "abcde"
regdcmd( cmd="set", data=var3 )
```

Using regd as a password agent from a script:

```
#!/usr/bin/bash

# In this script we get from regd a user password and use it for
# mounting a cifs partition on a remote machine.

passw="$(regd get-sec userPass)"

if [[ ! "${passw}" =~ ^1.+ ]]; then
	echo "Couldn't read the password."
	exit -1

mount.cifs //remote.host/backup "/mnt/backup" -o username=john,password="${passw:1}",rw
```

Installing
----------

To install *regd*, download the latest release from [here](https://github.com/nbdsp/regd/releases),
and then in the command line run:

	$ python setup.py install

This will install *regd* to the local python packages.

Running
-------

After installing __regd__ can be started either manually or with any scheduler 
like `systemd` or `cron`. __regd__ can run either as a local daemon, using a file as a socket, or it can run on a network IP address and function as a centralized settings server or data exchange server.

```
# For running as a local daemon:

$ regd start

# For running as a network server:

$ regd start --host some.hostname --port #####

# To send command to regd running locally on other user account:

$ regd get someVar --server-name someName

```


  Secure tokens file
---------------------------

Secure tokens can be stored in a gpg encrypted file, which is created
by encrypting a usual text file as follows:

	gpg --encrypt --recipient "<key description>" -o securefile.gpg textdata.txt

For creating encrypted data file, a regd user needs to have a private
encryption key. If a user doesn't have such a key, it can be generated 
with the command:

	gpg --gen-key

An unencrypted text file, from which the encrypted file is created, should
contain data in `<name=value>` pairs, where 'name' is the name or aliase
of the data (e.g. "myDBPassword"), and 'value' is the data itself:
	
`myDBPassword=ys7 5R-e%wi,P`

Lines with 'name=value' pairs can contain whitespaces, and, for convenience,
whitespaces surrounding the '=' sign are not considered a part of the name or value:

------- File privateinfo.txt -------
```
myPostgresDBPass = passphraseWithoutSpaces
myEmailPass = passphrase with spaces
```
-------- End of file ----------------


   Issues
------------

Issues can be reported at: https://github.com/nbdsp/safestor/issues/new
