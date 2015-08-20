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
__lastedited__="2015-08-20 16:15:38"

import sys, os, pwd, logging, signal, re
import configparser
import regd.defs as defs

# Loggers
log = logging.getLogger( defs.APPNAME )
logtok = logging.getLogger(defs.APPNAME + ".tok")
logcomm = logging.getLogger(defs.APPNAME + ".comm")


_sockfile = None


# Exceptions

class ISException( Exception ):
	''' InfoStore exception. '''
	def __init__( self, code, errCause = None, errMsg = None, moreInfo=None ):
		#curframe = inspect.currentframe()
		#calframe = inspect.getouterframes(curframe, 2)
		#self.raiser = calframe[1][3]		
		self.raiser = sys._getframe().f_back.f_code.co_name
		self.code = code
		self.cause = errCause
		if errMsg == None and code < len( errStrings ):
			self.msg = errStrings[code]
		else:
			self.msg = errMsg
		if moreInfo:
			self.msg += ": " + moreInfo

	def __str__( self, *args, **kwargs ):
		return "Exception {0} in {1}:  {2}: {3}".format( self.code,	self.raiser, self.msg, 
														self.cause )

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
# Error codes don't start with '1'
objectNotExists		 = 20
unrecognizedParameter= 21
unrecognizedSyntax	 = 22

errStrings = ["Program error", "Operation successfull", "Unknown data format", "Value doesn't exist", "Value already exists",
			"Operation failed", "Permission denied", 
			"Persistent tokens are not enabled on this server", "Cannot connect to server",
			"Client connection error", 
			'','','','','','','','','','',
			"Object doesn't exist", "Unrecognized parameter", "Unrecognized syntax"]

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
	log_level = getattr( logging, loglevel )
	log.setLevel( log_level )

	if not log.hasHandlers():
		# Console output ( for debugging )
		strlog = logging.StreamHandler()
		strlog.setLevel( loglevel )
		log.addHandler( strlog )
	
	if logtopics:
		if "tokens" in logtopics and not logtok.hasHandlers():
			logtok.setLevel(logging.DEBUG)
			strlogtok = logging.StreamHandler()
			strlogtok.setLevel( logging.DEBUG )
			bftok = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
			strlogtok.setFormatter( bftok )
			logtok.addHandler( strlogtok )
		if "comm" in logtopics and not logcomm.hasHandlers():
			logcomm.setLevel(logging.DEBUG)
			strlogcomm = logging.StreamHandler()
			strlogcomm.setLevel( logging.DEBUG )
			bfcomm = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
			strlogcomm.setFormatter( bfcomm )
			logcomm.addHandler( strlogcomm )
			
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
		servername = None
	else:
		if len( servername ) > 32:
			raise ISException( unknownDataFormat, server_string, 
							"The server name must not exceed 32 characters.")
		for c in "\\/:@":
			if c in servername:
				raise ISException( unknownDataFormat, server_string, 
								"Server name contains not permitted character: '{0}'".format( c ))
	
	return ( atuser, servername )

def get_filesock_addr( atuser=None, servername=None ):
	'''Composes and returns the file socket filename. Without 'servername' parameter 
	returns only the socket directory.'''
	
	tmpdir = os.getenv("TMPDIR", "/tmp")
	tmpdir += "/regd-" + defs.rversion
	if atuser:
		atuserid = pwd.getpwnam( atuser ).pw_uid
		sockdir = '{0}/{1}'.format( tmpdir, atuserid )
	else:
		userid = os.getuid()
		sockdir = '{0}/{1}'.format( tmpdir, userid )
		
	if not servername:
		_sockfile = None
	else:
		_sockfile = '{0}/.{1}.{2}'.format( sockdir, servername, defs.sockname )	
	return ( sockdir, _sockfile )
	
def parse_sockfile_name(sf):
	if sf.endswith(defs.sockname):
		sn = os.path.basename( sf )
		sn = sn[0:(len(sn) - ( len(defs.sockname) + 1 ) )]
		return ( 1, sn[1:], None)
	elif sf.endswith(defs.sockname + ".ip"):
		sn = os.path.basename( sf )
		sn = sn[0:(len(sn) - ( len(defs.sockname) + 3 + 1) )]
		host, _, port = sn.partition("_")
		return ( 2, host[1:], port )
	else:
		return ( 0, None, None )
	
def printMap( m, indent ):
	ret = ""
	for k,v in m.items():
		if isinstance( v, dict):
			ret += "{0:{width}}[{1}]\n".format("", k, width=(indent+1))
			ret += printMap( m[k], indent + 4 )
		else:
			ret += "{0:{width}} {1:20} : {2}\n".format("", k, v, width=(indent+1))
			
	return ret
	
def recvPack(sock, pack):
	data = bytearray()
	packlen = 0
	datalen = -1

	while packlen != datalen:
		try:
			newdata = sock.recv( 4096 )
		except OSError as e:
			raise ISException(clientConnectionError, moreInfo=e.strerror)
			
			
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
	
def createPacket( cpars : 'in map', bpack : 'out bytearray' ):
	'''Create a command packet for sending to a regd server.'''
	# Format: <packlen> <cmd|opt> <numparams> [<paramlen> <param>]...
	
	if not cpars.get("cmd", None):
		raise ISException( unknownDataFormat, "Command parameters must have 'cmd' field.")
	
	bpack.extend( (cpars["cmd"] + ' ').encode('utf-8') )
	if cpars.get("params"):
		bpack.extend( (str(len(cpars["params"])) + ' ' ).encode('utf-8'))
		for par in cpars["params"]:
			b = bytearray( par, encoding='utf-8')
			bpack.extend( (str(len(b)) + ' ' ).encode('utf-8'))
			bpack.extend( b )
	else:
		bpack.extend( b'0' )
	
	for k, v in cpars.items():
		if not k or k in ["cmd", "params"]:
			continue
		
		bpack.extend( (' ' + k + ' ').encode('utf-8') )
		if v and not(v is True):
			bpack.extend( (str(len(v)) + ' ' ).encode('utf-8'))
			for par in v:
				if type( par ) is str:
					b = bytearray( par, encoding='utf-8')
				elif type( par ) is bytearray or type( par ) is bytes:
					b = par
				else:
					raise ISException( unknownDataFormat, par )
				bpack.extend( (str(len(b)) + ' ' ).encode('utf-8') )
				bpack.extend( b )
		else:
			bpack.extend( b'0' )		
	
	
def createPacketFromLists(cmd : 'in list', opt : 'in list', bpack : 'out bytearray'):
	# Creating packet: <packlen> <cmd|opt> <numparams> [<paramlen> <param>]...
	if cmd:
		bpack.extend( (cmd[0] + ' ').encode('utf-8') )
		if cmd[1]:
			bpack.extend( (str(len(cmd[1])) + ' ' ).encode('utf-8'))
			for par in cmd[1]:
				b = bytearray( par, encoding='utf-8')
				bpack.extend( (str(len(b)) + ' ' ).encode('utf-8'))
				bpack.extend( b )
		else:
			bpack.extend( b'0' )
	
	if opt:
		for op in opt:
			if op:
				bpack.extend( (' ' + op[0] + ' ').encode('utf-8') )
				if op[1]:
					bpack.extend( (str(len(opt[1])) + ' ' ).encode('utf-8'))
					for par in opt[1]:
						b = bytearray( opt[1], encoding='utf-8')
						bpack.extend( (str(len(b)) + ' ' ).encode('utf-8') )
						bpack.extend( b )
				else:
					bpack.extend( b'0' )
	
def parsePacket( data : 'in bytes', cmdOptions : 'out list', cmdData : 'out list') -> str:	
	# Server commands and regd command line commands and options are two different sets:
	# the latter is the CL user interface, and the former is the internal communication 
	# protocol.
	# Regd client receives commands from the command line, converts it to server command 
	# syntax, and sends it in the form of command packet to the server.
	# Each packet contains exactly one command and related to it options, if any.
	# Format of command packets:
	# <COMMAND> <NUMPARAMS> [<PARAMLENGTH> <PARAM>] ... [OPTION NUMPARAMS PARAMLENGTH PARAM]...

	cmd = None
	while data:
		params=[]
		word, _, data = data.partition(b' ')
		if not data:
			raise ISException(unknownDataFormat, word + ' ' + data )
		numparams, _, data = data.partition(b' ')
		try:
			numparams = int( numparams.decode('utf-8') )
			word = word.decode('utf-8')
			
			for _ in range(0, numparams):
				paramlen, _, data = data.partition(b' ')
				paramlen = int( paramlen.decode('utf-8') )
				if not (paramlen <= len( data )): raise
				if not paramlen: raise 
				param = data[:paramlen]
				data = data[paramlen+1:]
				if word == "binary":
					params.append( bytes( param ) )
				else:
					params.append( param.decode('utf-8' ))				
			
			if word in defs.all_cmds:
				# One command per packet
				if cmd: raise 
				cmd = word
				if len( params ) == 0:
					cmdData = None
				else:
					cmdData.extend( params )
					
			elif word in defs.cmd_opts:
				cmdOptions.append(( word, params ))
				
			else:
				raise 
		except:
			raise ISException(unknownDataFormat, word)
		
	if not cmd:
		raise ISException(unknownDataFormat, "Command is not recognized.")
	
	return cmd

def composeResponse(bpack : 'out bytearray', code='1', *args):
	'''Response message has hierachical recursive format and can have any number of nested 
	levels. Message logically consists of opaque data chunks (ODC) composed into objects with a
	simple structure: each object contains the number of items it composed of, the items
	themselves and the type of each item: ODC or object.
	Format of an object: <ITEMTYPE> <NUMITEMS | ITEMSIZE> <ITEM> 
	args argument can contain ints, floats, strings, bytearrays, None, lists and dictionaries, 
	with the latter two also containing these types.
	'''
	def packObject( ob ):
		if ob is None:
			bpack.extend( ('N').encode('utf-8') )
		if type( ob ) is int:
			ba = bytearray( str(ob), encoding='utf-8')
			bpack.extend( ('I' + str(len(ba)) + ' ').encode('utf-8') )
			bpack.extend( ba )			
		elif type( ob ) is float:
			ba = bytearray( str(ob), encoding='utf-8')
			bpack.extend( ('F' + str(len(ba)) + ' ').encode('utf-8') )
			bpack.extend( ba )			
		elif type( ob ) is bytearray or type( ob ) is bytes:
			bpack.extend( ('B' + str(len(ob)) + ' ').encode('utf-8') )
			bpack.extend( ob )
		elif type( ob ) is list:
			bpack.extend( ( 'L' + str(len(ob) ) + ' ').encode('utf-8') )
			for item in ob:
				packObject(item)
		elif type( ob ) is dict:
			bpack.extend( ( 'D' + str(len(ob) * 2 ) + ' ').encode('utf-8') )
			for k,v in ob.items():
				packObject(k)
				packObject(v)				
		else: 
			ba = bytearray( str(ob), encoding='utf-8')
			bpack.extend( ('S' + str(len(ba)) + ' ').encode('utf-8') )
			bpack.extend( ba )
	
	bpack.extend( (code + ' ').encode('utf-8') )
	if not args:
		return packObject(None)
	
	if len( args ) > 1:
		bpack.extend( ( 'L' + str(len(args) ) ).encode('utf-8') )
		bpack.extend( b' ' )
	for item in args:
		packObject( item )
	
def parseResponse( 	resp : "byte array with server response",
					lres : "result list"):
	'''Function for parsing regd server response.'''
	def unpackObject( _data, seqout ):
		data = _data[0]
		hdr, _, data = data.partition(b' ')
		ot = hdr[0:1].decode('utf-8') # object type
		_data[0] = data
		if ot == 'N':
			seqout.append( None )
			return
		sz = int(hdr[1:]) # object size / number of items
		if ot == 'I':
			arr = data[:sz]
			data = data[sz:]
			seqout.append(int(arr.decode('utf-8')))
			_data[0] = data
		elif ot == 'F':
			arr = data[:sz]
			data = data[sz:]
			seqout.append(float(arr.decode('utf-8')))
			_data[0] = data					
		elif ot == 'B':
			arr = data[:sz]
			data = data[sz:]
			seqout.append(arr)
			_data[0] = data
		elif ot == 'S':
			arr = data[:sz]
			data = data[sz:]
			seqout.append(arr.decode('utf-8'))
			_data[0] = data
		elif ot == 'L':
			l = []
			#seqout.append( l )
			for _ in range(0, sz):
				unpackObject( _data, l )
			if len( l ) == 1:
				seqout.append( l[0] )
			elif len( l ) > 1:
				seqout.append( l )
					
		elif ot == 'D':
			m = {}
			seqout.append( m )
			for _ in range(0, int(sz/2)):
				l = []
				unpackObject( _data, l )
				if len( l ) > 1:
					raise ISException(unknownDataFormat, resp[:20], 
									moreInfo="Dictionary key is a compound object")
				k = l[0]
				l=[]
				unpackObject( _data, l )
				if len( l ) == 1:
					v = l[0]
				else:
					v = l
				m[k] = v				
	
	res, _, data = resp.partition( b' ' )
	if not data:
		raise ISException( unknownDataFormat, resp[:20])
	lres.append( res.decode('utf-8') )
	unpackObject([data], lres )
	

def getLog( n ):
	d = {}
	read_conf( d )
	if not "logfile" in d:
		return "Logging to a file isn't configured in regd.conf."
	logfile = d["logfile"]
	with open( logfile, "r" ) as f:
		ls = f.readlines()[-n:]
	return "".join(ls)

def clc( s ):
	return( s.replace("_", "-"))

def declc( s ):
	return( s.replace("-", "_"))
	
def clp( s ):
	return("--" + s.replace("_", "-"))
	
def getOptions(opts, *args):
	# opts - list of pairs with the first item being the option name
	# args - list of options to retrieve
	ret=[]
	for a in args:
		found = False
		for op in opts:
			if op[0] == a:
				ret.append(op[1])
				found = True
				break
		if not found:
			ret.append(None)
	
	return ret

def getSwitches(opts, *args):
	# opts - list of pairs with the first item being the option name
	# args - list of options to retrieve
	ret=[]
	for a in args:
		found = False
		for op in opts:
			if op[0] == a:
				ret.append(True)
				found = True
				break
		if not found:
			ret.append(False)
	
	return ret

def getOptionMap(opts):
	# opts - list of pairs with the first item being the option name
	ret={}
	for op in opts:
		if op[1]:
			ret[op[0]] = op[1]
		else:
			ret[op[0]] = None
	
	return ret

def removeOptions(opts, *args):
	if not opts:
		return
	for a in args:
		for i in range(0, len(opts)):
			if opts[i][0] == a:
				opts = opts[:i] + opts[(i+1):]
				i -= 1
				
def checkHostAddr( host, port ):
	if not re.match( "[a-zA-Z0-9\.-]+", host ):
		return ( "Host name contains invalid characters. Only numbers, letters, dots and ",
				"hyphens are allowed." )

	if len( host ) > 255:
		return( "Host name is too long." )

	if not re.match( "[0-9]+", port ):
		return( "Port number must only contain digits." )
		
	if int( port ) > 65536:
		return( "The number must be no greater than 65536." )
	
def printObject( ob, ind=0, endl='\n'):
	if type( ob ) is list:
		for o in ob:
			printObject( o, ind, endl )
	elif type( ob ) is dict:
		for k,v in ob.items():
			printObject(k, ind, " : ")
			printObject( v, 0 )
	elif type( ob ) is str:
		print( "{0}{1}".format( " " * ind, ob), end=endl)
	else:
		print( "{0}{1}".format( " " * ind, str( ob ) ), end=endl)
			
			
					