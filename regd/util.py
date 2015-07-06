'''
/********************************************************************
*	Module:			regd.util
*
*	Created:		Jul 5, 2015
*
*	Abstract:		Utilities.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*********************************************************************/
'''
__lastedited__="2015-07-06 00:29:45"

import sys, os, pwd, logging, signal
import configparser
import regd.defs as defs

# Loggers
log = None
logtok = None

_sockfile = None


# Exceptions

class ISException( Exception ):
	''' InfoStore exception. '''
	def __init__( self, code, errCause = None, errMsg = None, moreInfo=None ):
		self.code = code
		self.cause = errCause
		if errMsg == None and code < len( errStrings ):
			self.msg = errStrings[code]
		else:
			self.msg = errMsg
		if moreInfo:
			self.msg += ": " + moreInfo

	def __str__( self, *args, **kwargs ):
		return "{0} - {1} : {2}".format( self.code,	self.msg, self.cause )

programError		 = 0
success				 = 1
unknownDataFormat 	 = 2
valueNotExists		 = 3
valueAlreadyExists	 = 4
operationFailed		 = 5
permissionDenied	 = 6
persistentNotEnabled = 7
cannotConnectToServer= 8
clientConnectionError= 9
objectNotExists		 = 10

errStrings = ["Program error", "Operation successfull", "Unknown data format", "Value doesn't exist", "Value already exists",
			"Operation failed", "Permission denied", 
			"Persistent tokens are not enabled on this server", "Cannot connect to server",
			"Client connection error", "Object doesn't exist"]

class SignalHandler:
	def __init__(self):
		self.hmap = {}
	
	def push(self, sig, h):
		if sig not in self.hmap:
			self.hmap[sig] = [] 
			signal.signal( sig, self )
		self.hmap[sig].append( h )
		
	def pop(self, sig):
		if sig not in self.hmap or not self.hmap[sig]:
			raise ISException(objectNotExists, sig, "No handler found.")
		self.hmap[sig].pop()

	def __call__(self, sig, frame ):
		if sig in self.hmap:
			for i in range(len(self.hmap[sig]),0,-1):
				self.hmap[sig][i-1](sig, frame)

sigHandler = SignalHandler()

def setLog( loglevel, logtopics=None ):
	global log, logtok
	log = logging.getLogger( defs.APPNAME )
	log_level = getattr( logging, loglevel )
	log.setLevel( log_level )

	# Console output ( for debugging )
	strlog = logging.StreamHandler()
	strlog.setLevel( loglevel )
	bf = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
	strlog.setFormatter( bf )
	log.addHandler( strlog )
	
	logtok = logging.getLogger(defs.APPNAME + ".tok")
	if logtopics:
		if logtopics == "tokens":
			logtok.setLevel(logging.DEBUG)
			strlogtok = logging.StreamHandler()
			strlogtok.setLevel( logging.DEBUG )
			bftok = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
			strlogtok.setFormatter( bftok )
			logtok.addHandler( strlogtok )

def get_home_dir():
	if defs.homedir:
		return defs.homedir
	
	username = pwd.getpwuid(os.getuid())[0]

	if username:
		return os.path.expanduser( '~' + username )
	else:
		return ":"  # No home directory
			
def get_conf_dir():
	global confdir, homedir
	
	if defs.confdir:
		return defs.confdir
	
	if not defs.homedir:
		defs.homedir = get_home_dir()
		
	if defs.homedir == "-":
		return None
	
	confhome = os.getenv("XDG_CONFIG_HOME", defs.homedir + "/.config")
	return confhome + "/regd"
	
			
def read_conf( cnf ):
	cp = configparser.ConfigParser( interpolation=None, delimiters='=')
	cp.optionxform = str
	# First reading system-wide settings
	CONFFILE = "/etc/regd/regd.conf"
	if os.path.exists( CONFFILE ):
		cp.read( CONFFILE )

	CONFFILE = defs.confdir + "/regd.conf"
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
	tmpdir += "/regd-" + defs.rversion
	if atuser:
		atuserid = pwd.getpwnam( atuser ).pw_uid
		sockdir = '{0}/{1}'.format( tmpdir, atuserid )
	else:
		userid = os.getuid()
		sockdir = '{0}/{1}'.format( tmpdir, userid )
		
	_sockfile = '{0}/.{1}.{2}'.format( sockdir, servername, defs.sockname )	
	return ( sockdir, _sockfile )

def getcp():
	return {}
	
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
	m['num_of_sections'] = len( list(cp.keys()) )
	m['num_of_tokens'] = 0
	m['max_key_length'] = 0
	m['max_value_length'] = 0
	m['avg_key_length'] = 0
	m['avg_value_length'] = 0
	m['total_size_bytes'] = 0
	for sec in cp.values():
		for nam, val in sec.items:
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

def recvPack(sock, pack):
	data = bytearray()
	packlen = 0
	datalen = -1

	while packlen != datalen:
		newdata = sock.recv( 4096 )
			
		data.extend( newdata )
		datalen = len( data )
		if not packlen and datalen >= 10:
			# First chunk
			try:
				packlen = int( data[:10].decode('utf-8').strip() ) + 10
			except:
				log.debug("wrong format: %s" % (data.decode('utf-8')))
				raise ISException(unknownDataFormat)
			
	if not packlen:
		raise ISException(clientConnectionError, moreInfo="No data received")
	
	pack.extend( data )
		
def sendPack(sock, pack):
	packlen = "{0:<10}".format( len(pack) )
	cmdpack = bytearray( packlen, encoding = 'utf-8' )
	cmdpack.extend( pack )
	sock.sendall( cmdpack )		
			