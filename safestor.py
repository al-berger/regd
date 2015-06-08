#!/usr/bin/env python
'''********************************************************************
*	Module:			safestor
*	
*	File name:		safestor.py
*
*	Created:		2015-Apr-05 06:20:25 PM
*
*	Abstract:		Local info storage server. 
*
*	Copyright:		Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__="2015-06-08 09:09:23"

VERSION = (0, 3)
__version__ = '.'.join(map(str, VERSION[0:2]))
__description__ = 'Secure data cache'
__author__ = 'Albert Berger'
__author_email__ = 'alberger@gmail.com'
__homepage__ = 'https://github.com/nbdsp/safestor'
__license__ = 'BSD'

import sys, os, socket, signal, subprocess, logging, argparse, time, regex, pwd
from configparser import ConfigParser

APPNAME = "SafeStor"
THISFILE = os.path.basename( __file__ )
USAGE = ( "Usage: \n"
		"{0}  <item_name> - outputs the <item_name> data."   
		"{0} --start - starts server\n"
		"{0} --stops - stops server.\n\n"
		"{0} --add <key=value> - add data to cache.\n\n"
		).format( THISFILE )
EODMARKER = "%^&"
CMDMARKER = "&&&"
ITEMMARKER = "@#$"
GLSEC = "global"

server_userid = 1000

if server_userid == None:
	server_userid = os.getuid()
	
sockdir = '/var/run/user/{0}'.format( server_userid )
sockname = 'safestor.sock'
server_address = '{0}/.{1}'.format( sockdir, sockname )
homedir = pwd.getpwuid( server_userid )[5] 
#homedir = os.path.expanduser( '~' + os.getenv('LOGNAME') )
CONFFILE = homedir + "/.config/safestor/safestor.conf"

# Default encrypted file name
ENCFILE = homedir + "/.sec/safestor.gpg"
# Flag showing whether the default enc. file has been read
defencread = False

# Persistent storage file
PERSFILE = homedir + "/.config/safestor/persistent"		

tokens = ConfigParser()
sectokens = ConfigParser()
perstokens = ConfigParser()
tokens.optionxform = str
sectokens.optionxform = str
perstokens.optionxform = str

# Commands
START_SERVER		= "start"
STOP_SERVER			= "stop"
RESTART_SERVER		= "restart"
CHECK_SERVER		= "check"
LIST_TOKENS_PERS	= "list_pers"
LIST_TOKENS_CACHE	= "list_cache"
LIST_TOKENS_ALL		= "list_all"
SET_TOKEN			= "set"
SET_TOKEN_PERS		= "set_pers"
ADD_TOKEN 			= "add"
ADD_TOKEN_PERS		= "add_pers"
LOAD_TOKENS 		= "load"
LOAD_TOKENS_PERS	= "load_pers"
LOAD_FILE 			= "load_file"
LOAD_FILE_SEC 		= "load_file_sec"
GET_TOKEN 			= "get"
GET_TOKEN_SEC		= "get_sec"

# Logger
log = None

# Exceptions

class ISException( Exception ):
	''' InfoStore exception. '''
	def __init__(self, code, errCause=None, errMsg=None):
		self.code = code
		self.cause = errCause
		if errMsg == None and code < len( errStrings ):
			self.msg = errStrings[code]
		else:
			self.msg = errMsg
			
	def __str__(self, *args, **kwargs):
		return "{0}{1} [{2}]: {3} : {4}".format( self.code, APPNAME, 
								"ERROR" if self.code != 1 else "SUCESS", self.msg, self.cause )

programError		= 0
success				= 1
unknownDataFormat 	= 2
valueNotExists		= 3
valueAlreadyExists	= 4
operationFailed		= 5

errStrings = ["Program error", "Operation successfull", "Unknown data format", "Value doesn't exist", "Value already exists",
			"Operation failed"]


def signal_handler(signal, frame):
	os.unlink( server_address )
	sys.exit(1)
	
def read_sec_file( filename ):
	if not os.path.exists( ENCFILE ):
		log.error( "Cannot find encrypted data file. Exiting.")
		raise ISException( operationFailed, "File not found." )		

	try:
		ftxt = subprocess.check_output("gpg --textmode -d {0}".format( ENCFILE ), 
							shell=True, stderr=subprocess.DEVNULL )
	except subprocess.CalledProcessError as e:
		log.error( ftxt )
		raise ISException( operationFailed, e.output )	
		
	ftxt = ftxt.decode('utf-8')
	ltxt = ftxt.split("\n")
	
	curSect = GLSEC
	rgSection = "^\[(.+)\]$"
	for s in ltxt:
		if len(s) == 0 or s[0] == '#' or s[0] == '"':
			continue
		mSect = regex.match( rgSection, s )
		if mSect is not None:
			curSect = mSect.group( 1 )
			sectokens.add_section( curSect )
		else:
			add_token( sectokens, curSect + ":" + s )
		
def add_token( cp, tok, noOverwrite=False ):
	sec, _, opt = tok.rpartition( ":" )
	
	if not opt or opt.find( "=" ) == -1:
		raise ISException( unknownDataFormat, tok )
	
	key, _, val = opt.partition( "=" )
	
	if not sec:
		sec = GLSEC
	
	if not cp.has_section( sec ):
		cp.add_section( sec )
		
	if noOverwrite and cp.has_option( sec, key ):
		raise ISException( valueAlreadyExists, tok )
		
	cp[sec][key] = val
	
def get_token( cp, tok ):	
	sec, _, opt = tok.rpartition( ":" )
	
	if not opt:
		raise ISException( unknownDataFormat, tok )
	
	if not sec:
		sec = GLSEC
		
	if not cp.has_section( sec ) or not cp.has_option( sec, opt ):
		raise ISException( valueNotExists, tok )
	
	return cp[sec].get( opt )

def list_tokens( cp, sec=None ):
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

def contactServer( item ):
	'''
	"Client" function. Performs requests to a running server.
	Called from main() when a request to the server is made via CLI.
	'''
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	if item.find( "_sec " ) != -1 or item.endswith( "_sec" ):
		sock.settimeout( 30 )
	else:
		sock.settimeout(3)

	try:
		sock.connect( server_address )
	except OSError as er:
		log.error( "Socket error {0}: {1}\nServer address: {2}".format( 
												er.errno, er.strerror, server_address ) )
		sys.exit(-1)

	try:
		# Creating packet: <data><endOfDataMarker>
		bPacket = bytearray( item + EODMARKER, encoding='utf-8' )
		
		sock.sendall( bPacket )
		
		eodsize = len( EODMARKER )
		while True:
			data = sock.recv(4096)
			datalen = len( data )
			if datalen >= eodsize and data[-eodsize:].decode('utf-8') == EODMARKER:
				break
		
		sock.shutdown(socket.SHUT_RDWR)
		sock.close()
		
		return data[:-eodsize].decode('utf-8')
	except OSError as er:
		log.error( 
			"safestor: contactServer: Socket error {0}: {1}\nServer address: {2}\n".format( 
												er.errno, er.strerror, server_address ) )
		sys.exit(-1)


def startServer():
	global CONFFILE, PERSFILE, ENCFILE
	global sockdir, sockname, server_address 
	global defencread, server_userid
	
	if os.path.exists( server_address ):
		'''Socket file may remain after an unclean exit. Check if another server is running.'''
		try:
			# If the server is restarted, give the previous instance time to exit cleanly.
			time.sleep( 2 )
			res = subprocess.check_output(
						"ps -ef | grep '{0} --start' | grep -v grep".format( __file__ ), 
						shell=True)
			res = res.decode( 'utf-8' )
		except subprocess.CalledProcessError as e:
			if e.returncode != 1:
				log.error( "Check for already running server instance failed: {0} ".format( e.output ) )
				return -1
			else:
				res = ""
			
		if len( res ):
			if res.count("\n") > 1:
				'''Server is already running.'''
				log.warning( "Server is already running:\n{0}".format( res ))
				return 1
	
	try:
		os.unlink( server_address )
	except OSError:
		if os.path.exists( server_address ):
			raise

	if os.path.exists( CONFFILE ):
		with open( CONFFILE ) as f:
			for s in f:
				key,_,val = s.partition( "=" )
				if key.strip() == 'encfile':
					ENCFILE = val.strip()
	
	if os.path.exists( PERSFILE ):
		perstokens.read( PERSFILE )
				
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)
	signal.signal(signal.SIGHUP, signal_handler)
	signal.signal(signal.SIGABRT, signal_handler)
				
	eodsize = len( EODMARKER )
	cmdmarksize = len( CMDMARKER )
	itemmarksize = len( ITEMMARKER )
	log.info("Starting server...")
	sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
	sock.bind( server_address )

	sock.listen(1)
	
	while True:
		connection, client_address = sock.accept()
		log.debug( "safestor: Server: new connection")
		connection.settimeout(3)
		data = bytearray()
		try:
			while True:
				data.extend( connection.recv(4096) )
				datalen = len( data )
				if datalen >= eodsize and data[-eodsize:].decode('utf-8') == EODMARKER:
					break
			
			data = data[:-eodsize].decode('utf-8')
			log.debug( "safestor: Server: data received: {0}".format( data ))
			
			# Three major response codes: 
			# 0 - program error
			# 1 - success
			# 2 - operation unsuccessful (e.g. key doesn't exist)
			resp = "0"
			cmd = ""
			if data.startswith( CMDMARKER ):
				
				data = data[cmdmarksize:]
				cmd, _, data = data.partition( " " )
				
				if cmd == STOP_SERVER:
					resp = "1"
					
				if cmd == CHECK_SERVER:
					resp = "1Ready and waiting."
					
				if cmd == LIST_TOKENS_PERS:
					sects = data.split(",") if len(data) else None
					try:
						resp = "1" + list_tokens( perstokens, sects )
					except ISException as e:
						resp = str( e )
					
				if cmd == LIST_TOKENS_CACHE:
					sects = data.split(",") if len(data) else None
					try:
						resp = "1" + list_tokens( tokens, sects )
					except ISException as e:
						resp = str( e )
					
				if cmd == LIST_TOKENS_ALL:
					try:
						s = list_tokens( perstokens )
						s += list_tokens( tokens )
						resp = "1" + s
					except ISException as e:
						resp = str( e )
						
				elif cmd == ADD_TOKEN:
					'''Strict add: fails if the token already exists.'''
					try:
						add_token(tokens, data, noOverwrite=True)
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == SET_TOKEN:
					try:
						add_token(tokens, data)
						resp = "1"
					except ISException as e:
						resp = str( e )
										
				elif cmd == ADD_TOKEN_PERS:
					'''Strict add: fails if the token already exists.'''
					try:
						add_token(perstokens, data, noOverwrite=True)
						with open( PERSFILE, "w" ) as f:
							perstokens.write( f, True )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == SET_TOKEN_PERS:
					try:
						add_token(perstokens, data)
						with open( PERSFILE, "w" ) as f:
							perstokens.write( f, True )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == LOAD_TOKENS:
					try:
						newitems = []
						pl = data.find( ITEMMARKER )
						while pl != -1:
							newitem = data[:pl]
							add_token( tokens, newitem )
							data = data[(pl + itemmarksize):]
						
						add_token( tokens, data )
						resp = "1"
					except ISException as e:
						resp = str( e )
					
				elif cmd == GET_TOKEN:
					'''Get token. '''
					try:
						resp = "1" + get_token(tokens, data)
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
									read_sec_file( ENCFILE )
									defencread = True
							resp = "1" + get_token( sectokens, data)
						except ISException as e:
							resp = str( e )			
							
				elif cmd == LOAD_FILE:
					data = data[11:].strip()
					
				elif cmd == LOAD_FILE_SEC:
					if not len( data ):
						file = ENCFILE
					else:
						file = data
						
					try:
						read_sec_file( file )
						resp = "1"
					except ISException as e:
						resp = str( e )			
						
			else:
				try:
					resp = "1" + get_token(tokens, data)
				except ISException as e:
					resp = str( e )
						
			resp += EODMARKER

			try:
				connection.sendall( bytearray( resp, encoding='utf-8' ) )
			except OSError as er:
				log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
								er.errno, er.strerror, client_address ))
				
			if cmd == STOP_SERVER:
				log.info( "Stopping server.")
				os.unlink( server_address )
				return 0
				
		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()		

def main():
	"""
	- Query format: safestor.py <item>
	--start and --stop items start and stop server.
	"""
	global ENCFILE
	
	# Parsing command line
	
	class Item(argparse.Action):
		def __init__(self, option_strings, dest, nargs=None, **kwargs):
			if nargs is not None:
				pass
				#raise ValueError("nargs not allowed")
			super(Item, self).__init__(option_strings, dest, nargs, **kwargs)
	
		def __call__(self, parser, namespace, values=None, option_string=None):
			setattr(namespace, "itemcmd", True)
			setattr(namespace, "cmd", self.dest[:])
			setattr(namespace, "item", values)
			
	class ActionCmd(argparse.Action):
		def __call__(self, parser, namespace, values=None, option_string=None):
			setattr(namespace, "actioncmd", True)
			setattr(namespace, "cmd", self.dest[:])
			
	parser = argparse.ArgumentParser( 
		description = 'InfoStor : Secure information storage.'
	)
	group = parser.add_mutually_exclusive_group()
	parser.add_argument( 'token', nargs='?', help='Get a token')
	parser.add_argument( '--log-level', default = 'WARNING', help = 'DEBUG, INFO, WARNING, ERROR, CRITICAL' )
	group.add_argument( '--'+START_SERVER, action="store_true", help = 'Start server' )
	group.add_argument( '--'+STOP_SERVER, action="store_true", help = 'Stop server' )
	group.add_argument( '--'+RESTART_SERVER, action="store_true", help = 'Restart server' )
	group.add_argument( '--'+CHECK_SERVER, nargs=0, action=ActionCmd, help = 'Ping server' )
	group.add_argument( '--'+ADD_TOKEN, action=Item, help = 'Add a token' )
	group.add_argument( '--'+SET_TOKEN, action=Item, help = 'Set a token' )
	group.add_argument( '--'+ADD_TOKEN_PERS.replace('_', '-'), action=Item, help = 'Add a persistent token' )
	group.add_argument( '--'+SET_TOKEN_PERS.replace('_', '-'), action=Item, help = 'Set a persistent token' )
	group.add_argument( '--'+GET_TOKEN, action=Item, help = 'Get a token' )
	group.add_argument( '--'+GET_TOKEN_SEC.replace('_', '-'), action=Item, help = 'Get a secure token' )
	group.add_argument( '--'+LIST_TOKENS_ALL.replace('_', '-'), action=ActionCmd, nargs=0, help = 'List cached and persistent tokens' )
	group.add_argument( '--'+LIST_TOKENS_CACHE.replace('_', '-'), action=Item, nargs = '?', help = '--list-cache [section[,section]...]' )
	group.add_argument( '--'+LIST_TOKENS_PERS.replace('_', '-'), action=Item, nargs = '?', help = '--list-pers [section[,section]...]' )
	group.add_argument( '--'+LOAD_FILE_SEC.replace('_', '-'), action=Item, nargs = '?', help = 'Load encrypted file' )
	
	args = parser.parse_args()
	
	# Setting up logging
	
	global log
	log = logging.getLogger( APPNAME )
	log_level = getattr( logging, args.log_level )
	log.setLevel( log_level )
	
	# Console output ( for debugging )
	strlog = logging.StreamHandler()
	strlog.setLevel( log_level )
	bf = logging.Formatter("[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{")
	strlog.setFormatter(bf)	
	log.addHandler( strlog )
	
	# File output
	logfile = '/home/al/var/run/log.log'.format( os.getuid() )
	if not os.path.isfile(logfile):
		with open(logfile, 'w') as f:
			f.write("")
			
	filelog = logging.FileHandler( logfile )
	filelog.setLevel( logging.WARNING )
	log.addHandler( filelog )
	
	# Info screen output
	
	#iscrlog = utils.IScrLogger()
	#iscrlog.setLevel( logging.ERROR )
	#log.addHandler( iscrlog )	
	
	# Handling command line
	
	if not args.start:
		if not os.path.exists( server_address ):
			log.warning("Server isn't running.")
			return 1
	
	if args.start:
		return startServer()
	
	elif args.stop:
		if contactServer( CMDMARKER + STOP_SERVER ) != "1":
			log.error( "cmd 'stop': Cannot contact server." )
			return -1
	
	elif args.restart:
		if contactServer( CMDMARKER + STOP_SERVER ) != "1":
			log.error( "cmd 'restart': Cannot contact server." )
			return -1
		
		time.sleep( 1 )

		return startServer()
	
	elif hasattr( args, 'itemcmd' ):
		if args.item:
			res = contactServer( CMDMARKER + args.cmd + " " + args.item )
		else: 
			'''Default item'''
			res = contactServer( CMDMARKER + args.cmd )
		if res[0] != '1':
			if args.cmd.startswith("get"):
				print( "0", res )
			else:
				log.error( "itemcmd: Cannot contact server." )
			log.debug( res )
			return -1
		print( res )
		
	elif hasattr( args, "actioncmd" ):
		res = contactServer( CMDMARKER + args.cmd ) 
		if res[0] != '1':
			log.error( "actioncmd: Cannot contact server." )
			log.debug( res )
			return -1
		print(res[1:])

		
	return 0


if __name__ == "__main__":
	sys.exit( main() )
