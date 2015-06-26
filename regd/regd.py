#!/usr/bin/env python
'''********************************************************************
*	Package:		regd
*	
*	Module:			regd.py
*
*	Created:		2015-Apr-05 06:20:25 PM
*
*	Abstract:		Registry daemon. 
*
*	Copyright:		Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__ = "2015-06-26 05:56:12"

VERSION = ( 0, 5, 1, 12 )
__version__ = '.'.join( map( str, VERSION[0:3] ) )
__description__ = 'Registry daemon and data cache'
__author__ = 'Albert Berger'
__author_email__ = 'nbdspcl@gmail.com'
__homepage__ = 'https://github.com/nbdsp/regd'
__license__ = 'GPL'
rversion = '.'.join(map(str, VERSION[0:3]))+ '.r' + str(VERSION[3])

import sys, os, socket, signal, subprocess, logging, argparse, time, re, pwd, struct
import ipaddress
from datetime import datetime
from configparser import ConfigParser
import fcntl, __main__  # @UnresolvedImport

APPNAME = "regd"
THISFILE = os.path.basename( __file__ )
EODMARKER = "^&%"
CMDMARKER = "&&&"
GLSEC = "global"

# Privacy levels
PL_PRIVATE			= 1
PL_PUBLIC_READ		= 2
PL_PUBLIC			= 3

sockname = 'regd.sock'
homedir = None
data_fd = None
confdir = None

# Commands
START_SERVER		 = "start"
STOP_SERVER			 = "stop"
RESTART_SERVER		 = "restart"
CHECK_SERVER		 = "check"
REPORT_STAT			 = "report_stat"
REPORT_ACCESS		 = "report_access"
SHOW_LOG			 = "show_log"
LIST_TOKENS_PERS	 = "list_pers"
LIST_TOKENS_SESSION	 = "list_session"
LIST_TOKENS_ALL		 = "list_all"
SET_TOKEN			 = "set"
SET_TOKEN_PERS		 = "set_pers"
ADD_TOKEN 			 = "add"
ADD_TOKEN_PERS		 = "add_pers"
ADD_TOKEN_SEC		 = "add_sec"
LOAD_TOKENS 		 = "load"
LOAD_TOKENS_PERS	 = "load_pers"
LOAD_FILE 			 = "load_file"
LOAD_FILE_PERS		 = "load_file_pers"
LOAD_FILE_SEC 		 = "load_file_sec"
GET_TOKEN 			 = "get"
GET_TOKEN_PERS		 = "get_pers"
GET_TOKEN_SEC		 = "get_sec"
REMOVE_TOKEN		 = "remove"
REMOVE_TOKEN_PERS	 = "remove_pers"
REMOVE_TOKEN_SEC	 = "remove_sec"
REMOVE_SECTION		 = "remove_section"
REMOVE_SECTION_PERS	 = "remove_section_pers"
REMOVE_SECTION_SEC	 = "remove_section_sec"
CLEAR_SEC			 = "clear_sec"
CLEAR_SESSION		 = "clear_session"
TEST_START			 = "test_start"
TEST_CONFIGURE		 = "test_configure"
TEST_MULTIUSER_BEGIN = "test_multiuser_begin"
TEST_MULTIUSER_END 	 = "test_multiuser_end"

# Command groups

pubread_cmds = ( CHECK_SERVER, LIST_TOKENS_ALL, LIST_TOKENS_PERS, LIST_TOKENS_SESSION, 
			GET_TOKEN, GET_TOKEN_PERS )
secure_cmds = ( START_SERVER, STOP_SERVER, RESTART_SERVER, REPORT_ACCESS, REPORT_STAT, 
			ADD_TOKEN_SEC, GET_TOKEN_SEC, LOAD_FILE_SEC, REMOVE_TOKEN_SEC, REMOVE_SECTION_SEC, 
			CLEAR_SEC, SHOW_LOG)
pers_cmds = ( LIST_TOKENS_PERS, SET_TOKEN_PERS, ADD_TOKEN_PERS, LOAD_TOKENS_PERS, LOAD_FILE_PERS,
			GET_TOKEN_PERS, REMOVE_TOKEN_PERS, REMOVE_SECTION_PERS)
local_cmds = (SHOW_LOG, TEST_START, TEST_CONFIGURE, TEST_MULTIUSER_BEGIN, TEST_MULTIUSER_END)

# Loggers
log = None
logtok = None

# Exceptions

class ISException( Exception ):
	''' InfoStore exception. '''
	def __init__( self, code, errCause = None, errMsg = None ):
		self.code = code
		self.cause = errCause
		if errMsg == None and code < len( errStrings ):
			self.msg = errStrings[code]
		else:
			self.msg = errMsg

	def __str__( self, *args, **kwargs ):
		return "{0}{1} [{2}]: {3} : {4}".format( self.code, APPNAME,
								"ERROR" if self.code != 1 else "SUCESS", self.msg, self.cause )

programError		 = 0
success				 = 1
unknownDataFormat 	 = 2
valueNotExists		 = 3
valueAlreadyExists	 = 4
operationFailed		 = 5
permissionDenied	 = 6
persistentNotEnabled = 7

errStrings = ["Program error", "Operation successfull", "Unknown data format", "Value doesn't exist", "Value already exists",
			"Operation failed", "Permission denied", 
			"Persistent tokens are not enabled on this server"]


def signal_handler( signal, frame ):
	global _sockfile
	if _sockfile:
		os.unlink( _sockfile )
	sys.exit( 1 )
	
def setLog( loglevel, logtopics=None ):
	global log, logtok
	log = logging.getLogger( APPNAME )
	log_level = getattr( logging, loglevel )
	log.setLevel( log_level )

	# Console output ( for debugging )
	strlog = logging.StreamHandler()
	strlog.setLevel( loglevel )
	bf = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
	strlog.setFormatter( bf )
	log.addHandler( strlog )
	
	logtok = logging.getLogger(APPNAME + ".tok")
	if logtopics:
		if logtopics == "tokens":
			logtok.setLevel(logging.DEBUG)
			strlogtok = logging.StreamHandler()
			strlogtok.setLevel( logging.DEBUG )
			bftok = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
			strlogtok.setFormatter( bftok )
			logtok.addHandler( strlogtok )
			
def get_home_dir():
	global homedir
	if homedir:
		return homedir
	
	username = pwd.getpwuid(os.getuid())[0]

	if username:
		return os.path.expanduser( '~' + username )
	else:
		return ":"  # No home directory
			
def get_conf_dir():
	global confdir, homedir
	
	if confdir:
		return confdir
	
	if not homedir:
		homedir = get_home_dir()
		
	if homedir == "-":
		return None
	
	confhome = os.getenv("XDG_CONFIG_HOME", homedir + "/.config")
	return confhome + "/regd"
	
			
def read_conf( cnf ):
	cp = ConfigParser( delimiters=( "=" ) )
	# First reading system-wide settings
	CONFFILE = "/etc/regd/regd.conf"
	if os.path.exists( CONFFILE ):
		cp.read( CONFFILE )

	CONFFILE = confdir + "/regd.conf"
	if os.path.exists( CONFFILE ):
		cp.read( CONFFILE )

	for sec in cp.sections():
		for nam, val in cp.items( sec ):
			cnf[nam] = val
			
def parse_server_name( server_string ):
	atuser = None
	servername = None
	
	if server_string:
		if server_string.find( '@' ) != -1:
			atuser = server_string[0:server_string.index('@')]
			servername = server_string[(len(atuser) + 1):]
		else:
			servername = server_string
			
	if not servername:
		servername = "regd"
	else:
		if len( servername ) > 32:
			raise ISException( unknownDataFormat, server_string, 
							"The server name must not exceed 32 characters.")
	
	return ( atuser, servername )

def get_filesock_addr( atuser, servername ):
	tmpdir = os.getenv("TMPDIR", "/tmp")
	tmpdir += "/regd-" + rversion
	if atuser:
		atuserid = pwd.getpwnam( atuser ).pw_uid
		sockdir = '{0}/{1}'.format( tmpdir, atuserid )
	else:
		userid = os.getuid()
		sockdir = '{0}/{1}'.format( tmpdir, userid )
		
	_sockfile = '{0}/.{1}.{2}'.format( sockdir, servername, sockname )	
	return ( sockdir, _sockfile )

def read_sec_file( filename, cmd, tok ):
	if not os.path.exists( filename ):
		log.error( "Cannot find encrypted data file. Exiting." )
		raise ISException( operationFailed, "File not found." )

	try:
		cmd = cmd.replace( "FILENAME", "{0}" )
		ftxt = subprocess.check_output( cmd.format( filename ),
							shell = True, stderr = subprocess.DEVNULL )
	except subprocess.CalledProcessError as e:
		log.error( ftxt )
		raise ISException( operationFailed, e.output )

	ftxt = ftxt.decode( 'utf-8' )
	ltxt = ftxt.split( "\n" )

	curSect = GLSEC
	rgSection = "^\[(.+)\]$"
	for s in ltxt:
		if len( s ) == 0 or s[0] == '#' or s[0] == '"':
			continue
		mSect = re.match( rgSection, s )
		if mSect is not None:
			curSect = mSect.group( 1 )
			tok.add_section( curSect )
		else:
			add_token( tok, curSect + ":" + s )

def escaped( s, idx ):
	'''Determines if a character is escaped'''
	# TODO: I couldn't come up with a reliable way to determine whether a character is 
	# escaped if it's preceded with a backslash: 
	# >>> len('\=')
	# >>> 2
	# >>> len('\\=')
	# >>> 2
	# >>> len('\\a')
	# >>> 2
	# >>> len('\\\a')
	# >>> 2	
	# Because of this there is a rule that separators must not be preceded with a backslash.
	if not ( s and idx ):
		return False
	
	return ( s[idx-1] is '\\' )

				
def escapedpart( tok, sep, second=False ):
	'''Partition on non-escaped separators'''
	if not tok:
		return (None, None)
	idx = -1
	start = 1
	while True:
		idx = tok.find( sep, start )
		if ( idx == -1 ) or not escaped( tok, idx ):
			break
		start = idx + 1
	
	if idx == -1: 
		tok = tok.replace("\\"+sep, sep)
		return (None, tok) if second else ( tok, None )
	
	l, r = ( tok[0:idx], tok[(idx+1):] )
	l = l.replace("\\"+sep, sep)
	#r = r.replace("\\"+sep, sep)
		
	return (l, r)

def parse_token( tok, second=True ):
	logtok.debug( "tok: {0}".format( tok ) )
	sec, opt = escapedpart( tok, ":", True )
	if sec: sec = sec.strip()
	if opt: opt = opt.strip()
	logtok.debug( "section: {0} : option: {1}".format( sec, opt ) )
	
	if second:
		nam, val = escapedpart(opt, "=")
		nam = nam.strip() if nam else None
		val = val.strip() if val else None
	else:
		nam = opt
		val = None

	logtok.debug( "name: {0} = value: {1}".format( nam, val ) )

	if not sec:
		sec = GLSEC
		
	return (sec, nam, val)

def add_token( cp, tok, noOverwrite = False ):
	sec, nam, val = parse_token(tok)
	
	if not ( nam and val ):
		raise ISException( unknownDataFormat, tok ) 

	if not cp.has_section( sec ):
		cp.add_section( sec )

	if noOverwrite and cp.has_option( sec, nam ):
		raise ISException( valueAlreadyExists, tok )

	cp[sec][nam] = val

def get_token( cp, tok ):
	sec, opt, _ = parse_token( tok, False )
	
	if not opt:
		raise ISException( unknownDataFormat, tok )

	if not cp.has_section( sec ) or not cp.has_option( sec, opt ):
		raise ISException( valueNotExists, tok )

	return cp[sec].get( opt )

def remove_token( cp, tok ):
	sec, opt, _ = parse_token( tok, False )

	if not opt:
		raise ISException( unknownDataFormat, tok )

	if not cp.has_section( sec ) or not cp.has_option( sec, opt ):
		raise ISException( valueNotExists, tok )

	cp.remove_option( sec, opt )

def remove_section( cp, sec ):
	if not sec:
		sec = GLSEC

	if not cp.has_section( sec ):
		raise ISException( valueNotExists, sec )

	cp.remove_section( sec )

def list_tokens( cp, sec = None ):
	sects = []
	ret = ""
	if not sec:
		sects = cp.sections()
	else:
		sects += sec
	for sec in sects:
		if not cp.has_section( sec ):
			ret += "No such section: {0}\n".format( sec )
			continue
		ret += "[{0}]\n".format( sec )
		for nam, val in cp.items( sec ):
			ret += "   {0} = {1}\n".format( nam, val )

	return ret

def printMap( m, indent ):
	ret = ""
	for k,v in m.items():
		if type( v ) is dict:
			ret += "{0:{width}}[{1}]\n".format("", k, width=(indent+1))
			ret += printMap( m[k], indent + 4 )
		else:
			ret += "{0:{width}} {1:20} : {2}\n".format("", k, v, width=(indent+1))
			
	return ret
			
def statReg(cp):
	m={}
	m['num_of_sections'] = len( cp.sections() )
	m['num_of_tokens'] = 0
	m['max_key_length'] = 0
	m['max_value_length'] = 0
	m['avg_key_length'] = 0
	m['avg_value_length'] = 0
	m['total_size_bytes'] = 0
	for sec in cp.sections():
		for nam, val in cp.items( sec ):
			m['num_of_tokens'] += 1
			if len(nam) > m['max_key_length']:
				m['max_key_length'] = len(nam)
			if len(val) > m['max_value_length']:
				m['max_value_length'] = len(val)
			m['avg_key_length'] += len(nam)
			m['avg_value_length'] += len(val)
			m['total_size_bytes'] += sys.getsizeof(val) + sys.getsizeof(nam)
	if m['num_of_tokens']:
		m['avg_key_length'] /= m['num_of_tokens']
		m['avg_value_length'] /= m['num_of_tokens']
	return m
					
			
def Client( item, sockfile=None, host=None, port=None ):
	'''
	"Client" function. Performs requests to a running server.
	'''
	log.debug("item={0}; sock={1}; host={2}; port={3}".format( item, sockfile, host, port ))
	if host:
		if not port:
			return "0Error: port number is not provided."
		# Create an Internet socket
		sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	else:
		if not os.path.exists( _sockfile ):
			return "0Server isn't running on {0}.".format( sockfile )
				
		sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
		
	if item.find( "_sec " ) != -1 or item.endswith( "_sec" ):
		sock.settimeout( 30 )
	else:
		sock.settimeout( 3 )

	try:
		if host:
			sock.connect(( host, int(port) ))
		else:
			sock.connect( sockfile )
	except OSError as er:
		resp = "0regd: connectServer: Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port )
		return resp

	try:
		# Creating packet: <data><endOfDataMarker>
		bPacket = bytearray( item + EODMARKER, encoding = 'utf-8' )

		sock.sendall( bPacket )

		eodsize = len( EODMARKER )
		while True:
			data = sock.recv( 4096 )
			datalen = len( data )
			if datalen >= eodsize and data[-eodsize:].decode( 'utf-8' ) == EODMARKER:
				break

		sock.shutdown( socket.SHUT_RDWR )
		sock.close()

		return data[:-eodsize].decode( 'utf-8' )
	except OSError as er:
		resp = "0regd: Client: Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port )
		return resp


def Server( servername, sockfile=None, host=None, port=None, acc=PL_PRIVATE ):
	global data_fd
	
	if sockfile and os.path.exists( sockfile ):
		'''Socket file may remain after an unclean exit. Check if another server is running.'''
		try:
			# If the server is restarted, give the previous instance time to exit cleanly.
			time.sleep( 2 )
			res = subprocess.check_output( 
						"ps -ef | grep '{0} --start .* {1} ' | grep -v grep".format( 
											__main__.__file__, servername ),
						shell = True )
			res = res.decode( 'utf-8' )
		except subprocess.CalledProcessError as e:
			if e.returncode != 1:
				log.error( "Check for already running server instance failed: {0} ".format( e.output ) )
				return -1
			else:
				res = ""

		if len( res ):
			if res.count( "\n" ) > 1:
				'''Server is already running.'''
				log.warning( "Server is already running:\n{0}".format( res ) )
				return 1

		try:
			os.unlink( sockfile )
		except OSError:
			if os.path.exists( sockfile ):
				raise
			
	stat = {}
	stat["general"]={}
	stat["tokens"]={}
	stat["commands"]={}
	mcmd = stat["commands"]
	tokens = ConfigParser(interpolation = None)
	sectokens = ConfigParser( interpolation = None )
	perstokens = ConfigParser( interpolation = None )
	tokens.optionxform = str
	sectokens.optionxform = str
	perstokens.optionxform = str	

	# Default encrypted file name
	ENCFILE = homedir + "/.sec/safestor.gpg"
	# Flag showing whether the default enc. file has been read
	defencread = False
	# Command line command for reading encrypted file
	READ_ENCFILE_CMD = "gpg --textmode -d FILENAME"

	# Default token separator
	ITEMMARKER = "@#$"
	
	# Trusted
	trustedUserids = []
	trustedIps = []

	d = {}
	read_conf( d )
	if "encfile" in d:
		ENCFILE = d["encfile"]
	if "token_separator" in d:
		ITEMMARKER = d["token_separator"]
	if "encfile_read_cmd" in d:
		READ_ENCFILE_CMD = d["encfile_read_cmd"]
	if host and "trusted_ips" in d:
		ips = d["trusted_ips"]
		if ips:
			ips = ips.split(' ')
			for ip in ips:
				try:
					ipaddr = ipaddress.IPv4Network(ip)
				except ValueError:
					log.warning("Trusted IPv4 %s is not a valid IP mask." % (ip))
					continue
				trustedIps.append(ipaddr)
				
	elif not host and "trusted_users" in d:
		trustedNames = d["trusted_users"]
		if trustedNames:
			trustedNames = trustedNames.split(' ')
			for un in trustedNames:
				try:
					uid = pwd.getpwnam( un ).pw_uid
				except:
					continue
				trustedUserids.append(uid)

	if data_fd:
		perstokens.read( data_fd )

	signal.signal( signal.SIGINT, signal_handler )
	signal.signal( signal.SIGTERM, signal_handler )
	signal.signal( signal.SIGHUP, signal_handler )
	signal.signal( signal.SIGABRT, signal_handler )

	eodsize = len( EODMARKER )
	cmdmarksize = len( CMDMARKER )
	itemmarksize = len( ITEMMARKER )
	log.info( "Starting server..." )
	useruid = os.getuid()
	stat["general"]["time_started"] = str(datetime.now()).rpartition(".")[0] 
	timestarted = datetime.now()
	
	def prepareStat():
		nonlocal mcmd
		ret = ""
		m = statReg( tokens )
		ret += ( "\nSession tokens:\n------------------------\n")
		ret += printMap( m, 0 )
		m = statReg( perstokens )
		ret += ( "\nPersistent tokens:\n------------------------\n")
		ret += printMap( m, 0 )
		ret += ( "\nCommands:\n------------------------\n")
		ret += printMap( mcmd, 0 )
		return ret
	
	try:
		if host:
			sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
			sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
			sock.bind( ( host, int(port) ) )
		else:
			sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
			sock.bind( sockfile )
			os.chmod( sockfile, mode=0o777 )
			
	except OSError as e:
		print( "Cannot create or bind socket: ", e )
		return -1

	sock.listen( 1 )

	while True:
		connection, client_address = sock.accept()
		if not host:
			creds = connection.getsockopt( socket.SOL_SOCKET, socket.SO_PEERCRED, 
									struct.calcsize("3i"))
			pid, uid, gid = struct.unpack("3i", creds)
			log.info("new connection: pid: {0}; uid: {1}; gid: {2}".format( pid, uid, gid ) )
		else:
			log.info( "new connection: client address: %s" % ( str( client_address ) ) )

		connection.settimeout( 3 )
		data = bytearray()
		try:
			while True:
				data.extend( connection.recv( 4096 ) )
				datalen = len( data )
				if datalen >= eodsize and data[-eodsize:].decode( 'utf-8' ) == EODMARKER:
					break

			data = data[:-eodsize].decode( 'utf-8' )
			log.info( "command received: {0}".format( data ) )

			# Three response classes:
			# 0 - program error
			# 1 - success
			# >1 - operation unsuccessful (e.g. key doesn't exist)
			resp = "0"
			cmd = ""
			perm = False			 

			if data.startswith( CMDMARKER ):
				data = data[cmdmarksize:]
				cmd, _, data = data.partition( " " )
			else:
				cmd = GET_TOKEN
				
			if host:
				# IP-based server
				if not trustedIps:
					perm = True
				else :
					try:
						clientIp = ipaddress.IPv4Address(client_address[0])
					except ValueError:
						log.error("Client IP address format is not recognized.")
					else:
						for i in trustedIps:
							if clientIp in i:
								perm = True
								log.debug("Client IP is trusted.")
								break 
						if not perm:
							log.debug("Client IP is NOT trusted.")
			else:
				# File socket server
				if useruid == uid:
					perm = True
				elif uid in trustedUserids:
					perm = True
				elif cmd not in secure_cmds:
					if acc == PL_PUBLIC:
						perm = True
					elif acc == PL_PUBLIC_READ:
						if cmd in pubread_cmds:
							perm = True 

			if not perm:
				resp = str( ISException( permissionDenied, cmd ) )
			elif not data_fd and cmd in pers_cmds:
				resp = str( ISException(persistentNotEnabled))
			else:
				mcmd[cmd] = 1 if cmd not in mcmd else mcmd[cmd]+1
				
				if cmd == STOP_SERVER:
					resp = "1"

				if cmd == CHECK_SERVER:
					resp = "1Up and running since {0}\nUptime:{1}.".format(	
							str(timestarted).rpartition(".")[0], 
							str(datetime.now() - timestarted).rpartition(".")[0])
				
				if cmd == REPORT_ACCESS:
					resp = "1{0}".format( acc )
					
				if cmd == REPORT_STAT:
					resp = "1" + prepareStat()
					
				if cmd == LIST_TOKENS_PERS:
					sects = data.split( "," ) if len( data ) else None
					try:
						resp = "1" + list_tokens( perstokens, sects )
					except ISException as e:
						resp = str( e )

				if cmd == LIST_TOKENS_SESSION:
					sects = data.split( "," ) if len( data ) else None
					try:
						resp = "1" + list_tokens( tokens, sects )
					except ISException as e:
						resp = str( e )

				if cmd == LIST_TOKENS_ALL:
					try:
						s = list_tokens( tokens )
						if data_fd:
							s += list_tokens( perstokens )
						resp = "1" + s
					except ISException as e:
						resp = str( e )

				elif cmd == ADD_TOKEN:
					'''Strict add: fails if the token already exists.'''
					try:
						add_token( tokens, data, noOverwrite = True )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == SET_TOKEN:
					try:
						add_token( tokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == ADD_TOKEN_PERS:
					'''Strict add: fails if the token already exists.'''
					try:
						add_token( perstokens, data, noOverwrite = True )
						perstokens.write( data_fd, True )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == SET_TOKEN_PERS:
					try:
						add_token( perstokens, data )
						perstokens.write( data_fd, True )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == LOAD_TOKENS:
					try:
						pl = data.find( ITEMMARKER )
						while pl != -1:
							newitem = data[:pl]
							add_token( tokens, newitem )
							data = data[( pl + itemmarksize ):]

						add_token( tokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == LOAD_TOKENS_PERS:
					try:
						pl = data.find( ITEMMARKER )
						while pl != -1:
							newitem = data[:pl]
							add_token( perstokens, newitem )
							data = data[( pl + itemmarksize ):]

						add_token( perstokens, data )
						perstokens.write( data_fd, True )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == GET_TOKEN:
					'''Get a token. '''
					try:
						resp = "1" + get_token( tokens, data )
					except ISException as e:
						resp = str( e )

				elif cmd == GET_TOKEN_PERS:
					'''Get a persistent token. '''
					try:
						resp = "1" + get_token( perstokens, data )
					except ISException as e:
						resp = str( e )

				elif cmd == GET_TOKEN_SEC:
					''' Get secure token. '''
					if not len( data ):
						resp = "0No token specified."
					else:
						try:
							if not sectokens.sections():
								'''Sec tokens are not read yet. Read the default priv. file.'''
								if not defencread:
									read_sec_file( ENCFILE, READ_ENCFILE_CMD, sectokens )
									defencread = True
							resp = "1" + get_token( sectokens, data )
						except ISException as e:
							resp = str( e )

				elif cmd == LOAD_FILE:
					'''Load tokens from a file.'''
					try:
						if os.path.exists( data ):
							tokens.read( data )
							resp = "1"
						else:
							resp = "{0}File not found: {1}".format( valueNotExists, data )
					except OSError as e:
						resp = "{0}Cannot read the file: {1}".format( operationFailed, e.strerror )

				elif cmd == LOAD_FILE_PERS:
					'''Add persistent tokens from a file.'''
					try:
						if os.path.exists( data ):
							perstokens.read( data )
							perstokens.write( data_fd, True )
							resp = "1"
						else:
							resp = "{0}File not found: {1}".format( valueNotExists, data )
					except OSError as e:
						resp = "{0}Cannot read the file: {1}".format( operationFailed, e.strerror )

				elif cmd == LOAD_FILE_SEC:
					if not len( data ):
						file = ENCFILE
					else:
						file = data

					try:
						read_sec_file( file, READ_ENCFILE_CMD, sectokens  )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == REMOVE_TOKEN:
					try:
						remove_token( tokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == REMOVE_SECTION:
					try:
						remove_section( tokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == REMOVE_TOKEN_PERS:
					try:
						remove_token( perstokens, data )
						perstokens.write( data_fd, True )
						resp = "1"
					except ISException as e:
						resp = str( e )

				elif cmd == REMOVE_SECTION_PERS:
					try:
						remove_section( perstokens, data )
						perstokens.write( data_fd, True )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == REMOVE_TOKEN_SEC:
					try:
						remove_token( sectokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == REMOVE_SECTION_SEC:
					try:
						remove_section( sectokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == CLEAR_SEC:
					sectokens = ConfigParser()
					resp = "1"

				elif cmd == CLEAR_SESSION:
					sectokens = ConfigParser()
					tokens = ConfigParser()
					resp = "1"
						
			resp += EODMARKER

			try:
				connection.sendall( bytearray( resp, encoding = 'utf-8' ) )
			except OSError as er:
				log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
								er.errno, er.strerror, client_address ) )

			if cmd == STOP_SERVER and perm:
				log.info( "Stopping server." )
				if sockfile:
					os.unlink( sockfile )
				return 0

		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()

def main(*kwargs):
	global homedir, confdir, log, logtok, _sockfile, data_fd

	# Parsing command line

	class Item( argparse.Action ):
		def __init__( self, option_strings, dest, nargs = None, **kwargs ):
			if nargs is not None:
				pass
				# raise ValueError("nargs not allowed")
			super( Item, self ).__init__( option_strings, dest, nargs, **kwargs )

		def __call__( self, parser, namespace, values = None, option_string = None ):
			setattr( namespace, "itemcmd", True )
			setattr( namespace, "cmd", self.dest[:] )
			setattr( namespace, "item", values )

	class ActionCmd( argparse.Action ):
		def __call__( self, parser, namespace, values = None, option_string = None ):
			setattr( namespace, "actioncmd", True )
			setattr( namespace, "cmd", self.dest[:] )

	def clp( s ):
		return("--" + s.replace("_", "-"))
	
	parser = argparse.ArgumentParser( 
		description = 'regd : Registry server.'
	)
	
	group = parser.add_mutually_exclusive_group()
	parser.add_argument( 'token', nargs = '?', help = 'Get a token' )
	parser.add_argument( '--log-level', default = 'WARNING', help = 'DEBUG, INFO, WARNING, ERROR, CRITICAL' )
	parser.add_argument( '--log-topics', help = 'For debugging purposes.' )
	parser.add_argument( '--server-name', help = 'The name of the server instance.' )
	parser.add_argument( '--host', help = 'Run the server on an Internet socket with the specified hostname.' )
	parser.add_argument( '--port', help = 'Run the server on an Internet socket with the specified port.' )
	parser.add_argument( '--access', help = 'Access level for the server: private, public_read or public.' )
	parser.add_argument( '--datafile', help = 'File for reading and storing persistent tokens.' )
	parser.add_argument( '--no-verbose', action='store_true', help = 'Only output return code numbers.' )
	group.add_argument( '--version', action='store_true', help = 'Print regd version.' )
	group.add_argument( clp(START_SERVER), action = "store_true", help = 'Start server' )
	group.add_argument( clp(STOP_SERVER), action = "store_true", help = 'Stop server' )
	group.add_argument( clp(RESTART_SERVER), action = "store_true", help = 'Restart server' )
	group.add_argument( clp(CHECK_SERVER), nargs = 0, action = ActionCmd, help = 'Ping server' )
	group.add_argument( clp(REPORT_ACCESS), nargs = 0, action = ActionCmd, help = 'Report the server\'s permission level.' )
	group.add_argument( clp(REPORT_STAT), nargs = 0, action = ActionCmd, help = 'Report the server\'s statistics.' )
	group.add_argument( clp(SHOW_LOG), metavar="N", nargs='?', const='10', help = 'Show the last N lines of the log file (if log is enabled).' )
	group.add_argument( clp(ADD_TOKEN), action = Item, metavar = "TOKEN", help = 'Add a token' )
	group.add_argument( clp(SET_TOKEN), action = Item, metavar = "TOKEN", help = 'Set a token' )
	group.add_argument( clp(ADD_TOKEN_PERS), action = Item, metavar = "TOKEN", help = 'Add a persistent token' )
	group.add_argument( clp(SET_TOKEN_PERS), action = Item, metavar = "TOKEN", help = 'Set a persistent token' )
	group.add_argument( clp(ADD_TOKEN_SEC), action = Item, metavar = "TOKEN", help = 'Add a secure token' )
	group.add_argument( clp(LOAD_TOKENS), action = Item, metavar = "TOKENS", help = 'Add tokens' )
	group.add_argument( clp(LOAD_TOKENS_PERS), action = Item, metavar = "TOKENS", help = 'Add persistent tokens' )
	group.add_argument( clp(GET_TOKEN), action = Item, metavar = "NAME", help = 'Get a token' )
	group.add_argument( clp(GET_TOKEN_PERS), action = Item, metavar = "NAME", help = 'Get a persistent token' )
	group.add_argument( clp(GET_TOKEN_SEC), action = Item, metavar = "NAME", help = 'Get a secure token' )
	group.add_argument( clp(LIST_TOKENS_ALL), action = ActionCmd, nargs = 0, help = 'List cached and persistent tokens' )
	group.add_argument( clp(LIST_TOKENS_SESSION), action = Item, metavar = "SECTIONS", nargs = '?', help = '--list-session [section[,section]...]' )
	group.add_argument( clp(LIST_TOKENS_PERS), action = Item, metavar = "SECTIONS", nargs = '?', help = '--list-pers [section[,section]...]' )
	group.add_argument( clp(LOAD_FILE), action = Item, metavar = "FILENAME", help = 'Load tokens from a file' )
	group.add_argument( clp(LOAD_FILE_PERS), action = Item, metavar = "FILENAME", help = 'Add persistent tokens from a file' )
	group.add_argument( clp(LOAD_FILE_SEC), action = Item, metavar = "FILENAME", nargs = '?', help = 'Load tokens from encrypted file' )
	group.add_argument( clp(REMOVE_TOKEN), action = Item, metavar = "NAME", help = 'Remove a token' )
	group.add_argument( clp(REMOVE_TOKEN_PERS), action = Item, metavar = "NAME", help = 'Remove a persistent token' )
	group.add_argument( clp(REMOVE_TOKEN_SEC), action = Item, metavar = "NAME", help = 'Remove a secure token' )
	group.add_argument( clp(REMOVE_SECTION), action = Item, metavar = "SECTION", help = 'Remove a section' )
	group.add_argument( clp(REMOVE_SECTION_PERS), action = Item, metavar = "SECTION", help = 'Remove a persistent section' )
	group.add_argument( clp(REMOVE_SECTION_SEC), action = Item, metavar = "SECTION", help = 'Remove a secure section' )
	group.add_argument( clp(CLEAR_SEC), action = ActionCmd, help = 'Remove all secure tokens' )
	group.add_argument( clp(CLEAR_SESSION), action = ActionCmd, help = 'Remove all session and secure tokens' )
	group.add_argument( clp(TEST_START), action = 'store_true', help = 'Start test' )
	group.add_argument( clp(TEST_CONFIGURE), action='store_true', help = 'Configure test' )
	group.add_argument( clp(TEST_MULTIUSER_BEGIN), action='store_true', help = 'Start regd server on this account for multiuser test.' )
	group.add_argument( clp(TEST_MULTIUSER_END), action='store_true', help = 'End multiuser test' )

	args = parser.parse_args(*kwargs)
	
	if args.version:
		print( rversion )
		return 0
	
	# Setting up logging
	
	setLog( args.log_level, args.log_topics )

	# Setting up server name
	
	try:
		atuser, servername = parse_server_name( args.server_name )
	except ISException as e:
		print( e )
		return e.code
	log.debug("Server name: %s ; atuser: %s" % (servername, atuser))
		
	userid = os.getuid()
	homedir = get_home_dir()
	confdir = get_conf_dir()

	log.debug("userid: %i ; homedir: %s ; confdir: %s  " % (userid, homedir, confdir))
	
	d = {}
	read_conf( d )
	
	# Setting up server address
	
	host = args.host
	port = args.port
	_sockfile = None
	sockdir = None
	
	if ( host or port ) and not ( host and port ):
		print( ( "Error: regd not started. For running regd on an internet address both "
				"host name and port number should be specified." ) )
		return 1
	
	if not host:
		'''Server runs on a UNIX domain socket.'''
		sockdir, _sockfile = get_filesock_addr( atuser, servername )
		log.debug("sockdir: %s ; sockfile: %s  " % (sockdir, _sockfile))
	else:
		log.debug("host: %s ; port: %s  " % (host, port))
	
	# File log
	if "logfile" in d:
		logfile = d["logfile"]
		if not os.path.isfile( logfile ):
			
			with open( logfile, 'w' ) as f:
				f.write( "" )

		filelog = logging.FileHandler( logfile )
		filelog.setLevel( logging.WARNING )
		log.addHandler( filelog )
	
	# Test module
	tstdir=os.path.dirname(os.path.realpath(__file__)) + "/testing"
	tst = tstdir + "/tests.py"

	# Test helper module.
	tsthelp = tstdir+"/test_help.py"

	# Handling command line
	
	# Server commands

	if args.start:
		
		# Setting up start configuration
		
		if atuser and userid:
			log.error( "Server cannot be started with server name containing '@'.")
			return 1
		if not host:
			try:
				os.makedirs( sockdir, mode=0o777, exist_ok=True )
				os.chmod( sockdir, mode=0o777 )
			except Exception as e:
				print("Error: cannot create temporary file socket directory. Exiting.")
				return -1
		
		# Permission level 
		
		acc = PL_PRIVATE
		if args.access:
			if args.access == "private":
				pass
			elif args.access == "public-read":
				acc = PL_PUBLIC_READ
			elif args.access == "public":
				acc = PL_PUBLIC
			else:
				print( "Unknown access mode. Must be: 'private', 'public-read' or 'public'")
				return 1
		log.debug("Permission level: %s" % args.access )
		
		# Data file
		
		# Default data directory
		DATADIR = confdir + "/data/"
	
		# Checking regd.conf for datadir
		if "datadir" in d:
			DATADIR = d["datadir"]
			if DATADIR and DATADIR[-1] != '/':
				DATADIR = DATADIR + "/"
			
		if not os.path.exists( DATADIR ):
			try:
				os.makedirs( DATADIR )
			except OSError as e:
				DATADIR = ""
				
		log.debug( "datadir: %s" % DATADIR )
		
		# Checking --datafile command line option
		datafile = args.datafile
		if datafile:
			if datafile == "None":
				datafile = None
			else:
				if not os.path.exists( datafile ):
					print( "Error: data file doesn't exist: \"{0}\".".format( datafile ),
						"Server is not started.")
					return -1
		elif DATADIR:
			# Composing the default data file name
			if host:
				datafile = host + "." + port + ".data"
			else:
				datafile = servername + ".data"
			
			datafile = DATADIR + datafile
		
		log.debug( "datafile: %s" % datafile )
		
		if datafile:
			# Obtaining the lock
			try:
				data_fd = open( datafile, "w" )
				data_fd = fcntl.lockf( data_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB )
			except OSError as e:
				print("Error: data file \"{0}\" could not be opened.".format(datafile), 
				"Probably it's already opened by another process. Server is not started.")
				return -1
		else:
			print( "Server's data file is not specified. Persistent tokens are not enabled.")
			
		log.info( "Starting %s server %s : %s " % (args.access, 
						(servername,host)[bool(host)], (_sockfile, port)[bool(host)]  ))
		return Server( servername, _sockfile, host, port, acc )

	elif args.stop:
		if Client( CMDMARKER + STOP_SERVER, _sockfile, host, port ) != "1":
			if not args.no_verbose:
				log.error( "cmd 'stop': Cannot contact server." )
			return -1

	elif args.restart:
		res = Client( CMDMARKER + REPORT_ACCESS, _sockfile, host, port )
		if Client( CMDMARKER + STOP_SERVER, _sockfile, host, port ) != "1":
			log.error( "cmd 'restart': Cannot contact server." )
			return -1
		
		if res[0] != '1':
			print( "Error: Could not get the permission level of the current server instance.",
				"Server stopped and didn't restarted.")
			return -1  

		time.sleep( 1 )

		return Server( servername, _sockfile, host, port, int(res[1]) )

	elif hasattr( args, 'itemcmd' ):
		if args.item:
			res = Client( CMDMARKER + args.cmd + " " + args.item, _sockfile, host, port )
		else:
			'''Default item'''
			res = Client( CMDMARKER + args.cmd, _sockfile, host, port )
		if res[0] != '1':
			if args.cmd.startswith( "get" ):
				print( "0", res )
			elif res[0] == '0' :
				log.error( "Cannot contact server." )
			else:
				log.error( res[1:] )
			log.debug( res )
			return -1
		print( res )

	elif hasattr( args, "actioncmd" ):
		res = Client( CMDMARKER + args.cmd, _sockfile, host, port )
		if res[0] != '1':
			log.error( res )
			return -1
		print( res )
	
	# Local commands
	
	elif args.show_log:
		with open( logfile, "r" ) as f:
			ls = f.readlines()[-int(args.show_log):]
			[print( x.strip('\n')) for x in ls ]
			
	elif args.test_configure:
		subprocess.call( ["python", tsthelp, "--test-configure"])
		
	elif args.test_start:
		print("\nIt's recommended to shutdown all regd server instances before testing.")
		ans = input("\nPress 'Enter' to begin test, or 'q' to quit.")
		if ans and ans in 'Qq':
			return 0
		print("Setting up test, please wait...")
		subprocess.call( ["python", "-m", "unittest", "regd.testing.tests.currentTest"])
		
	elif args.test_multiuser_begin:
		subprocess.Popen( [tsthelp, "--test-multiuser-begin"])

	elif args.test_multiuser_end:
		subprocess.Popen( [tsthelp, "--test-multiuser-end"])	
	
	
	return 0


if __name__ == "__main__":
	sys.exit( main(sys.argv[:] ) )
