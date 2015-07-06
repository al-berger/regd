#!/usr/bin/env python
'''********************************************************************
*	Package:		regd
*	
*	Module:			regd.regd
*
*	Created:		2015-Apr-05 06:20:25 PM
*
*	Abstract:		Registry daemon. 
*
*	Copyright:		Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__ = "2015-07-06 05:22:14"

import sys, os, socket, subprocess, logging, argparse, time
from regd.util import ISException, unknownDataFormat, objectNotExists, cannotConnectToServer
from regd.defs import *  # @UnusedWildImport
import regd.util as util, regd.defs as defs
log = None

THISFILE = os.path.basename( __file__ )

def signal_handler( signal, frame ):
	if util._sockfile:
		os.unlink( util._sockfile )
	sys.exit( 1 )
	
def connectToServer( sockfile=None, host=None, port=None, tmout=3 ):
	if host:
		if not port:
			raise ISException( unknownDataFormat, "Port number is not provided." )
		# Create an Internet socket
		sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	else:
		if not os.path.exists( sockfile ):
			raise ISException( objectNotExists, sockfile, "Server's socket file doesn't exist" )
				
		sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
		
	sock.settimeout( tmout )

	try:
		if host:
			sock.connect(( host, int(port) ))
		else:
			sock.connect( sockfile )
	except OSError as er:
		raise ISException( cannotConnectToServer, 
						"Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port ) )
	
	return sock	

def checkConnection(sockfile=None, host=None, port=None):
	try:
		sock = connectToServer(sockfile, host, port, 3)
	except ISException:
		return False
	
	sock.shutdown( socket.SHUT_RDWR )
	sock.close()
	return True
	
def Client( cmd, opt, sockfile=None, host=None, port=None ):
	'''
	"Client" function. Performs requests to a running server.
	'''
	log.debug("cmd={0}; opt={1}; sock={2}; host={3}; port={4}".format( 
									cmd, opt, sockfile, host, port ))
	
	tmout = 3
	if cmd[0].find( "_sec " ) != -1 or cmd[0].endswith( "_sec" ):
		tmout = 30
		
	try:
		sock = connectToServer(sockfile, host, port, tmout)
	except ISException as e:
		return str(e)

	try:
		# Creating packet: <packlen> <cmd|opt> <datalen> [data]...
		bpack = bytearray()
		if cmd:
			bpack.extend( (cmd[0] + ' ').encode('utf-8') )
			if cmd[1]:
				b = bytearray( cmd[1], encoding='utf-8')
				bpack.extend( (str(len(b)) + ' ' ).encode('utf-8'))
				bpack.extend( b )
			else:
				bpack.extend( b'0' )
		
		if opt:
			for op in opt:
				if op:
					bpack.extend( (' ' + op[0] + ' ').encode('utf-8') )
					if op[1]:
						b = bytearray( opt[1], encoding='utf-8')
						bpack.extend( (str(len(b)) + ' ' ).encode('utf-8') )
						bpack.extend( b )
					else:
						bpack.extend( b'0' )
		
		util.sendPack(sock, bpack)
		data = bytearray()
		util.recvPack(sock, data)

		sock.shutdown( socket.SHUT_RDWR )
		sock.close()

		return data[10:].decode( 'utf-8' )
	except OSError as er:
		resp = "0regd: Client: Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port )
		return resp

def main(*kwargs):
	global log

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
			
	cmdoptions = []
	
	class CmdParam( argparse.Action ):
		def __call__( self, parser, namespace, values, option_string = None ):
			if not values:
				raise ValueError("Command parameter must have a value")
			cmdoptions.append( ( self.dest[:], values ) )
			
	class CmdSwitch( argparse.Action ):
		def __call__( self, parser, namespace, values=None, option_string = None ):
			if values:
				raise ValueError("Command switch cannot have values")
			cmdoptions.append( ( self.dest[:], None ) )

	def clp( s ):
		return("--" + s.replace("_", "-"))
	
	parser = argparse.ArgumentParser( 
		description = 'regd : Registry server.'
	)
	
	#parser.add_argument( 'token', nargs = '?', help = 'Get a token' )
	# Regd options
	parser.add_argument( '--log-level', default = 'WARNING', help = 'DEBUG, INFO, WARNING, ERROR, CRITICAL' )
	parser.add_argument( '--log-topics', help = 'For debugging purposes.' )
	parser.add_argument( '--server-name', help = 'The name of the server instance.' )
	parser.add_argument( '--host', help = 'Run the server on an Internet socket with the specified hostname.' )
	parser.add_argument( '--port', help = 'Run the server on an Internet socket with the specified port.' )
	parser.add_argument( '--access', help = 'Access level for the server: private, public_read or public.' )
	parser.add_argument( '--datafile', help = 'File for reading and storing persistent tokens.' )
	parser.add_argument( '--no-verbose', action='store_true', help = 'Only output return code numbers.' )
	parser.add_argument( '--auto-start', action='store_true', help = 'If regd server is not running, start it before executing the command.' )
	# Commands
	group = parser.add_mutually_exclusive_group()
	group.add_argument( '--version', action='store_true', help = 'Print regd version.' )
	group.add_argument( clp(START_SERVER), action = "store_true", help = 'Start server' )
	group.add_argument( clp(STOP_SERVER), action = "store_true", help = 'Stop server' )
	group.add_argument( clp(RESTART_SERVER), action = "store_true", help = 'Restart server' )
	group.add_argument( clp(CHECK_SERVER), nargs = 0, action = ActionCmd, help = 'Ping server' )
	group.add_argument( clp(REPORT), nargs = 0, action = Item, choices = rep_opts, help = 'Report the specified server\'s info.' )
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
	group.add_argument( clp(LIST), action = Item, nargs = 0, help = 'List session and persistent tokens' )
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
	# Command options
	parser.add_argument( clp( DEST ), action = CmdParam, help = "The name of the section to which the command applies")
	parser.add_argument( clp( TREE ), action = CmdParam, help = "The name of the section to which the command applies")
	
	if not cmdoptions:
		cmdoptions = None

	args = parser.parse_args(*kwargs)
	
	if args.version:
		print( defs.rversion )
		return 0
	
	# Setting up logging
	
	util.setLog( args.log_level, args.log_topics )
	log = util.log

	# Setting up server name
	
	try:
		atuser, servername = util.parse_server_name( args.server_name )
	except ISException as e:
		print( e )
		return e.code
	log.debug("Server name: %s ; atuser: %s" % (servername, atuser))
		
	userid = os.getuid()
	defs.homedir = util.get_home_dir()
	defs.confdir = util.get_conf_dir()

	log.debug("userid: %i ; homedir: %s ; confdir: %s  " % (userid, defs.homedir, defs.confdir))
	
	d = {}
	util.read_conf( d )
	
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
		sockdir, _sockfile = util.get_filesock_addr( atuser, servername )
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
	#tst = tstdir + "/tests.py"

	# Test helper module.
	tsthelp = tstdir+"/test_help.py"

	# Handling command line
	
	# Server commands
	
	if args.auto_start:
		if not checkConnection(_sockfile, host, port):
			opts=[__file__, "--start"]
			if host: 
				opts.append("--host");
				opts.append(host)
			if port: 
				opts.append("--port");
				opts.append(port)
			if args.server_name: 
				opts.append("--server-name");
				opts.append(args.server_name)
			if args.access: 
				opts.append("--access");
				opts.append(args.access)
			if args.datafile: 
				opts.append("--datafile");
				opts.append(args.datafile)
			if args.log_level:
				opts.append("--log-level");
				opts.append(args.log_level)
			log.info("The server isn't running. Autostarting with arguments:%s" % (str(opts)))
			subprocess.Popen(opts)
			time.sleep(2)

	if args.start:
		import regd.serv as serv
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
		
		acc = defs.PL_PRIVATE
		if args.access:
			if args.access == "private":
				pass
			elif args.access == "public-read":
				acc = defs.PL_PUBLIC_READ
			elif args.access == "public":
				acc = defs.PL_PUBLIC
			else:
				print( "Unknown access mode. Must be: 'private', 'public-read' or 'public'")
				return 1
		log.debug("Permission level: %s" % args.access )
		
		# Data file
		
		# Default data directory
		DATADIR = defs.confdir + "/data/"
	
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
			if not os.path.exists( datafile ):
				fp = open( datafile, "w")
				fp.write("")
				fp.close()				
		
		log.debug( "datafile: %s" % datafile )
			
		log.info( "Starting %s server %s : %s " % (args.access, 
						(servername,host)[bool(host)], (_sockfile, port)[bool(host)]  ))
		return serv.Server( servername, _sockfile, host, port, acc, datafile )

	elif args.stop:
		if Client( (STOP_SERVER, None ), None, _sockfile, host, port ) != "1":
			if not args.no_verbose:
				log.error( "cmd 'stop': Cannot contact server." )
			return -1

	elif args.restart:
		resAcc = Client( ( REPORT, ACCESS ), None, _sockfile, host, port )
		resDf = Client( ( REPORT, DATAFILE ), None, _sockfile, host, port )
		if Client( ( STOP_SERVER, None ), None, _sockfile, host, port ) != "1":
			log.error( "cmd 'restart': Cannot contact server." )
			return -1
		
		if resAcc[0] != '1':
			print( "Error: Could not get the permission level of the current server instance.",
				"Server stopped and didn't restarted.")
			return -1  
		if resDf[0] != '1':
			print( "Error: Could not get the data file name of the current server instance.",
				"Server stopped and didn't restarted.")
			return -1  

		time.sleep( 1 )

		return serv.Server( servername, _sockfile, host, port, int(resAcc[1]), resDf[1] )

	elif hasattr( args, 'itemcmd' ):
		if args.item:
			res = Client( (args.cmd, args.item), cmdoptions, _sockfile, host, port )
		else:
			'''Default item'''
			res = Client( ( args.cmd, None ), cmdoptions, _sockfile, host, port )
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
		res = Client( ( args.cmd, None ), cmdoptions, _sockfile, host, port )
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
