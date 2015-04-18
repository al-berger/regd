  Safestor
============

Safestor is a local service which helps to use confidential data
such as passwords, etc., stored in encrypted form, from within any 
program or script. It enables a programmer or admin to avoid storing 
non-encrypted confidential data in program and script source files.

   Features
---------------
- Responds to data requests by outputting required decrypted data to stdout.
- Can run either as a server or in separate runs.
- Confidential data is secured by gpg encryption with the user's key.


Install
-------

To install safestor, simply:

	$ pip install safestor.py

This will add 'safestor.py' inside the local python bin folder.


   Usage
-----------
`safestor <item_name>` - returns the decrypted data stored with alias "item_name"
`safestor --start` - starts server
`safestor --stop` - stops server


  Confidential data file
---------------------------

Private data is stored in a gpg encrypted file, which is created
by encrypting a usual text file as follows:

`gpg --encrypt --recipient "<key description>" -o securefile.gpg textdata.txt`

For creating encrypted data file, a safestor user needs to have a private
encryption key. If a user doesn't have such a key, it can be generated 
with command:

`gpg --gen-key`

Unencrypted text file, from which encrypted file is created, should
contain data in the `<key=value>` pairs, where 'key' is the name or aliase
of the confidential text, and 'value' is the confidential text itself:
	
`<item_name>=<item_text>`

The line with key/value pair should not contain whitespaces that are not 
part of the key or value. For example:

------- File privateinfo.txt -------
```
myPostgresDBPass=h&gsjY68jslD
myEmailPass=passphrase with spaces
```
-------- End of file ----------------


   Using safestor
---------------------

Information in the encrypted file can be obtained from within other 
programs by calling safestor with the name of the required data and reading
the decrypted data from the stdout output of safestor. 

Request to safestor for data is done by running the command:

`safestor <item_name>`

For example:

------ File bashscript1.sh --------- 	
```shell
#!/usr/bin/bash

MYDBPASS=$(safestor.py MyPostgresDB 2>/dev/null)

if [[ -z "${MYDBPASS}" ]]; then
	echo Cannot get auth info. Exiting.
	exit -1
fi
```
----------- End of file -------------

Similar calls can be made from programs and scripts in any other programming
language.

( Note, that stderr stream of is used by safestor for outputting error 
messages, so the stderr output should be distinguished from the 
stdout output, which contains the required data. )


   Running modes
--------------------

Safestor can work either as constantly running server or in individual runs, 
when each query to safestor is served in a separate program run, where 
safestor exits after responding the query without starting the server. 

When running as server, safestor stores the data in computer's memory so the 
user doesn't need to enter the password multiple times.  When the server stops, 
all cached data is automatically erased from the computer's memory.


   Configuration
---------------------

Encrypted data file name can be either default `$HOME/.sec/safestor.gpg`, or
can be specified in the configuration file `$HOME/.config/safestor/safestor.conf`
in the form:

`encfile = /path/to/encrypted/file`


   Issues
------------

Issues can be reported at: https://github.com/nbdsp/safestor/issues/new
