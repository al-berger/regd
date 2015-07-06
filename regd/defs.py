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
__lastedited__="2015-07-06 06:16:56"

VERSION = ( 0, 6, 0, 16 )
__version__ = '.'.join( map( str, VERSION[0:3] ) )
__description__ = 'Registry daemon and data cache'
__author__ = 'Albert Berger'
__author_email__ = 'nbdspcl@gmail.com'
__homepage__ = 'https://github.com/nbdsp/regd'
__license__ = 'GPL'
rversion = '.'.join(map(str, VERSION[0:3]))+ '.r' + str(VERSION[3])

sockname 			= 'regd.sock'

APPNAME 			= "regd"
# End-of-data marker 
EODMARKER 			= "^&%"
# Default token separator
ITEMMARKER 			= "@#$"
# Default command for loading secure tokens
READ_ENCFILE_CMD 	= "gpg --textmode -d FILENAME"
	
# Privacy levels
PL_PRIVATE			= 1
PL_PUBLIC_READ		= 2
PL_PUBLIC			= 3

homedir 			= None
confdir 			= None

# Commands
START_SERVER		= "start"
STOP_SERVER			= "stop"
RESTART_SERVER		= "restart"
CHECK_SERVER		= "check"
REPORT				= "report"
SHOW_LOG			= "show_log"
LIST				= "ls"
SET_TOKEN			= "set"
SET_TOKEN_PERS		= "set_pers"
ADD_TOKEN 			= "add"
ADD_TOKEN_PERS		= "add_pers"
ADD_TOKEN_SEC		= "add_sec"
LOAD_TOKENS 		= "load"
LOAD_TOKENS_PERS	= "load_pers"
LOAD_FILE 			= "load_file"
LOAD_FILE_PERS		= "load_file_pers"
LOAD_FILE_SEC 		= "load_file_sec"
GET_TOKEN 			= "get"
GET_TOKEN_PERS		= "get_pers"
GET_TOKEN_SEC		= "get_sec"
REMOVE_TOKEN		= "remove"
REMOVE_TOKEN_PERS	= "remove_pers"
REMOVE_TOKEN_SEC	= "remove_sec"
REMOVE_SECTION		= "remove_section"
REMOVE_SECTION_PERS	= "remove_section_pers"
REMOVE_SECTION_SEC	= "remove_section_sec"
CLEAR_SEC			= "clear_sec"
CLEAR_SESSION		= "clear_session"
TEST_START			= "test_start"
TEST_CONFIGURE		= "test_configure"
TEST_MULTIUSER_BEGIN= "test_multiuser_begin"
TEST_MULTIUSER_END 	= "test_multiuser_end"

# Command options
DEST				= "dest"
SESSION				= "session"
PERS				= "pers"
ALL					= "all"
TREE				= "tree"

# Report options
ACCESS 				= "access"
STAT				= "stat"
DATAFILE			= "datafile"

# Command groups
all_cmds = ( START_SERVER, STOP_SERVER, RESTART_SERVER, CHECK_SERVER, REPORT,
			SHOW_LOG, LIST, SET_TOKEN, 
			SET_TOKEN_PERS, ADD_TOKEN, ADD_TOKEN_PERS, ADD_TOKEN_SEC, LOAD_TOKENS, LOAD_TOKENS_PERS,
			LOAD_FILE, LOAD_FILE_PERS, LOAD_FILE_SEC, GET_TOKEN, GET_TOKEN_PERS, GET_TOKEN_SEC,
			REMOVE_TOKEN, REMOVE_TOKEN_PERS, REMOVE_TOKEN_SEC, REMOVE_SECTION, REMOVE_SECTION_PERS,
			REMOVE_SECTION_SEC, CLEAR_SEC, CLEAR_SESSION, TEST_START, TEST_CONFIGURE,
			TEST_MULTIUSER_BEGIN, TEST_MULTIUSER_END)
pubread_cmds = ( CHECK_SERVER, LIST, GET_TOKEN, GET_TOKEN_PERS )
secure_cmds = ( START_SERVER, STOP_SERVER, RESTART_SERVER, REPORT, 
			ADD_TOKEN_SEC, GET_TOKEN_SEC, LOAD_FILE_SEC, REMOVE_TOKEN_SEC, REMOVE_SECTION_SEC, 
			CLEAR_SEC, SHOW_LOG)
pers_cmds = ( SET_TOKEN_PERS, ADD_TOKEN_PERS, LOAD_TOKENS_PERS, LOAD_FILE_PERS,
			GET_TOKEN_PERS, REMOVE_TOKEN_PERS, REMOVE_SECTION_PERS)
pers_opts = (PERS)
local_cmds = (SHOW_LOG, TEST_START, TEST_CONFIGURE, TEST_MULTIUSER_BEGIN, TEST_MULTIUSER_END)
cmd_opts = ( DEST, SESSION, PERS, ALL )
rep_opts = (ACCESS, STAT, DATAFILE)