  regd
=========

Regd is a registry service (like Windows registry) where other programs and 
computer users can keep and retrieve back various information such
as configuration settings, dynamic data, etc.

Regd can be used both via command line and through sockets.

Regd can securely handle confidential data. A user can load to
regd an encrypted file with confidential data (e.g. database 
password) and regd will function as a keyring-agent or password
manager, keeping this data in RAM until the user clears it out.

Regd can keep data temporarily or it can permanently store data on disk 
and load it automatically during startup.

Use cases of regd include:

- password agent (or more generally secure data cache) for providing other prorgrams 
and scripts with data which is read from encrypted file (or loaded with some other 
secure method), is always kept in RAM and is never stored in files in unencrypted form.

- interprocess communication agent for exchanging data between any number of programs,
where one program can write data and others read, or many write and one reads, or
many write and many read, etc.

- centralized persistent storage of user scripts' configuration settings, data, etc.
With regd scripts and programs can persistently store and retrieve any data with 
just one command. E.g. in a bash script this can look as follows:

`confSetting="$(regd --get-pers "someScript: someSetting")"`  
`someData="abcde"`  
`regd --set-pers "someScript: someData = ${someData}"`

- centralized settings or data exchange server running on an IP address in a network,
where other machines in the network can store and retrieve data in the same way
as was shown for the local usage. (In this use case the security of data exchange
within network should be ensured through the appropriate configuration of access
levels within network with `iptables`, etc.)

## Examples of using regd

From command line:

```
$ regd --start
$ regd --add "some variable = some value"
1
$ regd --get "some variable"
1some value
$ regd --add-pers "SOME APP: some setting = 1234"
1
$ regd --list-all
[global]
    some variable = some value
[SOME APP]
    some setting = 1234
$ regd --check
1Ready and waiting.
$ regd --stop
```

Via sockets:

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

passw="$(regd --get-sec userPass)"

if [[ ! "${passw}" =~ ^1.+ ]]; then
	echo "Couldn't read the password."
	exit -1

passw="${passw:1}"
mount.cifs //remote.host/backup "/mnt/backup" -o username=john,password="${passw}",rw
```

Install
-------

To install *regd*, download the latest release from [here](https://github.com/nbdsp/regd/releases),
and then in the command line run:

	$ python setup.py install

This will install *regd* to the local python packages.
After installing *regd* can be started either manually:

```
# For running as a local daemon
$ regd --start
```


  Secure tokens file
---------------------------

Secure tokens can stored in a gpg encrypted file, which is created
by encrypting a usual text file as follows:

	gpg --encrypt --recipient "<key description>" -o securefile.gpg textdata.txt

For creating encrypted data file, a regd user needs to have a private
encryption key. If a user doesn't have such a key, it can be generated 
with command:

	gpg --gen-key

An unencrypted text file, from which the encrypted file is created, should
contain data in `<name=value>` pairs, where 'name' is the name or aliase
of the secure text (e.g. "myDBPassword"), and 'value' is the secure text itself:
	
`myDBPassword=ys7 5R-e%wi,P`

Lines with name/value pairs should not contain whitespaces that are not 
parts of the key or value. For example:

------- File privateinfo.txt -------
```
myPostgresDBPass=h&gsjY68jslD
myEmailPass=passphrase with spaces
```
-------- End of file ----------------


   Issues
------------

Issues can be reported at: https://github.com/nbdsp/safestor/issues/new
