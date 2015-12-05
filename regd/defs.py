'''
/********************************************************************
*	Module:			regd.defs
*
*	Created:		Jul 5, 2015
*
*	Abstract:		Definitions.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*
*********************************************************************/
'''
__lastedited__ = "2015-12-04 08:11:16"

import regd.app as app
from regd.app import APPNAME

VERSION = ( 0, 6, 'pre6', 30 )
__version__ = '.'.join( [str( x ) for x in VERSION[0:3]] )
__description__ = 'Registry daemon and data cache'
__author__ = 'Albert Berger'
__author_email__ = 'nbdspcl@gmail.com'
__homepage__ = 'https://github.com/nbdsp/regd'
__license__ = 'GPL'
rversion = '.'.join( [str( x ) for x in VERSION[0:3]] ) + '.r' + str( VERSION[3] )

sockname 			 = 'regd.sock'
app.APPNAME 		 = "regd"
# Default command for loading secure tokens
READ_ENCFILE_CMD 	 = "gpg --textmode -d FILENAME"

# Privacy levels
PL_PRIVATE			 = 1
PL_PUBLIC_READ		 = 2
PL_PUBLIC			 = 3

# Commands
START_SERVER		 = "start"
STOP_SERVER			 = "stop"
RESTART_SERVER		 = "restart"
CHECK_SERVER		 = "check"
REPORT				 = "what"
INFO				 = "info"
IF_PATH_EXISTS		 = "is_path"
GETATTR				 = "getattr"
SETATTR				 = "setattr"
LIST				 = "ls"
ADD_TOKEN 			 = "add"
ADD_TOKEN_SEC		 = "add_sec"
COPY_FILE			 = "cp"
LOAD_FILE 			 = "load_file"
LOAD_FILE_SEC 		 = "load_file_sec"
GET_TOKEN 			 = "get"
GET_TOKEN_SEC		 = "get_sec"
REMOVE_TOKEN		 = "rm"
REMOVE_TOKEN_SEC	 = "remove_sec"
CREATE_SECTION		 = "mkdir"
CREATE_SECTION_SEC	 = "mkdir_sec"
REMOVE_SECTION		 = "rmdir"
REMOVE_SECTION_SEC	 = "rmdir_sec"
RENAME				 = "mv"
CLEAR_SEC			 = "clear_sec"
CLEAR_SESSION		 = "clear_session"
SHOW_LOG			 = "show_log"
TEST_START			 = "test_start"
TEST_CONFIGURE		 = "test_configure"
TEST_MULTIUSER_BEGIN = "test_multiuser_begin"
TEST_MULTIUSER_END 	 = "test_multiuser_end"
HELP 				 = "help"
VERS				 = "version"

# Regd options
SERVER_NAME			 = "server_name"
LOG_LEVEL			 = "log_level"
LOG_TOPICS			 = "log_topics"

# Command options
DEST				 = "dest"
SESSION				 = "session"
PERS				 = "pers"
ALL					 = "all"
TREE				 = "tree"
NOVALUES			 = "no_values"
FORCE				 = "force"
SERVER_SIDE			 = "server_side"
FROM_PARS			 = "from_pars"
ATTRS				 = "attrs"
BINARY				 = "binary"
RECURS				 = "recursively"
SUM					 = "sum"

# Report ("what") options
ACCESS 				 = "access"
STAT				 = "stat"
DATAFILE			 = "datafile"

# Command groups
all_cmds = ( ADD_TOKEN, ADD_TOKEN_SEC, CHECK_SERVER, CLEAR_SEC, CLEAR_SESSION, COPY_FILE,
			CREATE_SECTION, CREATE_SECTION_SEC, GETATTR, GET_TOKEN, GET_TOKEN_SEC, HELP,
			IF_PATH_EXISTS, INFO, LIST, LOAD_FILE, LOAD_FILE_SEC, REMOVE_SECTION, REMOVE_SECTION_SEC,
			REMOVE_TOKEN, REMOVE_TOKEN_SEC, REPORT, RESTART_SERVER, SETATTR, START_SERVER,
			STOP_SERVER, TEST_CONFIGURE, TEST_MULTIUSER_BEGIN, TEST_MULTIUSER_END, TEST_START,
			VERS, )
pubread_cmds = ( CHECK_SERVER, LIST, GET_TOKEN, IF_PATH_EXISTS )
secure_cmds = ( START_SERVER, STOP_SERVER, RESTART_SERVER, REPORT,
			ADD_TOKEN_SEC, GET_TOKEN_SEC, LOAD_FILE_SEC, REMOVE_TOKEN_SEC, REMOVE_SECTION_SEC,
			CLEAR_SEC )
pers_opts = ( PERS )
local_cmds = ( TEST_START, TEST_CONFIGURE, TEST_MULTIUSER_BEGIN, TEST_MULTIUSER_END )
# For executing these commands on server they must come with --server-side switch
nonlocal_cmds = ( SHOW_LOG, VERS )
cmd_opts = ( DEST, SESSION, PERS, ALL, TREE, NOVALUES, FORCE, SERVER_SIDE, FROM_PARS, ATTRS,
			BINARY, RECURS, SUM )
rep_opts = ( ACCESS, STAT, DATAFILE )

# Add token modes
overwrite 	 = 0
noOverwrite = 1
sumUp 		 = 2  # arithmetic adding for numbers and concatenating for strings and binaries

# Data file directive mark
dirMark = "//"

# Data file directives
# include <filePath> <relSectPath>
dirInclude = dirMark + "include"
dirAattributes = dirMark + "attributes"
