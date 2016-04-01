#!/usr/bin/env python
'''********************************************************************
*	Package:		regd
*
*	Module:			regd.cli
*
*	Created:		2015-Apr-05 06:20:25 PM
*
*	Abstract:		Registry daemon.
*
*	Copyright:		Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__ = "2016-01-26 12:12:01"

import sys, os, socket, subprocess, logging, argparse, time
from collections import defaultdict
import regd.util as util
from regd.app import clc, declc, clp
from regd.app import IKException, ErrorCode
import regd.defs as defs
import regd.app as app
import regd.rgs as rgs

THISFILE = os.path.basename( __file__ )

USAGE = '''
Usage:

regd <COMMAND> [PARAMETER] [OPTIONS]...

Commands:

start                      Start server
stop                       Stop server
restart                    Restart server
check                      Check server
add	<TOKEN1> [TOKEN2]...   Add token
get <TOKEN>		           Get token value
remove <TOKEN>             Remove token
remove-section <SECTION>   Remove section
clear-session              Remove all session tokens
load-file <FILENAME>       Read tokens from a file
ls [SECTION] [--tree]      List tokens
show-log [N]               Show N last lines of the log file

For more information please read the regd manual.
'''


def connectToServer( sockfile = None, host = None, port = None, tmout = 3 ):
	'''Makes connection to server.'''
	if host:
		if not port:
			raise IKException( ErrorCode.unknownDataFormat, "Port number is not provided." )
		sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	else:
		if not os.path.exists( sockfile ):
			raise IKException( ErrorCode.objectNotExists, sockfile, "Server's socket file doesn't exist" )

		sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
		sock.setsockopt( socket.SOL_SOCKET, socket.SO_PASSCRED, 1 )

	sock.settimeout( tmout )

	try:
		if host:
			sock.connect( ( host, int( port ) ) )
		else:
			sock.connect( sockfile )
	except OSError as er:
		raise IKException( ErrorCode.cannotConnectToServer,
						"Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port ) )

	return sock

def checkConnection( sockfile = None, host = None, port = None ):
	'''Checks connection to server.'''
	return Client( { "cmd": defs.CHECK_SERVER }, sockfile, host, port )[0]


def Client( cpars, sockfile = None, host = None, port = None ):
	'''"Client" function. Performs requests to a running server.'''
	util.log.debug( "cpars={0}; sock={1}; host={2}; port={3}".format( 
									cpars, sockfile, host, port ) )

	if not cpars.get( "cmd", None ):
		raise IKException( ErrorCode.unknownDataFormat, "Command parameters must have 'cmd' field." )

	tmout = 3

	try:
		data = bytearray()
		bpack = util.createPacket( cpars )
		util.logcomm.debug( "sending packet: {0}".format( bpack ) )

		try:
			sock = connectToServer( sockfile, host, port, tmout )
			util.sendPack( sock, bpack )
			util.recvPack( sock, data )
		except IKException as e:
			return False, [str( e )]

		util.logcomm.debug( "received packet: {0}".format( data ) )

		sock.shutdown( socket.SHUT_RDWR )
		sock.close()
		lres = []
		if len( data ) < 11:
			lres = ['0', 'Server returned empty response']
		else:
			lres = util.parsePacket( data[10:] )
			util.logcomm.debug( "parsed packet: {0}".format( lres ) )
		if len( lres ) == 2:
			if type( lres[1] ) is list and len( lres[1] ) == 1:
				ret = lres[1][0]
			else:
				ret = lres[1]
		else:
			ret = lres[1:] 
		return ( lres[0] == '1', ret )
	except OSError as er:
		return False, ["regd: Client: Socket error {0}: {1}\nsockfile: {2}; host: {3}; port: {4}".format( 
												er.errno, er.strerror, sockfile, host, port )]


def isServerCmd( cpars ):
	'''Checks whether the command is solely for communicating with server.'''
	cmd = cpars.get( "cmd", None )
	if not cmd:
		return False
	if cmd not in defs.local_cmds:
		if not cmd in defs.nonlocal_cmds:
			return True
		elif defs.SERVER_SIDE in cpars:
			return True
	return False

def doServerCmd( copts, sockfile, host, port ):
	'''Calls Client() with some pre- and postprocessing.'''

	if copts["cmd"] == defs.LOAD_FILE and not copts.get( "server_side", None ):
		files = []
		for fname in copts["params"]:
			if not os.path.exists( fname ):
				print( "File not found: ", fname )
				return -1
			with open( fname ) as f:
				files.append( f.read() )

		copts["params"] = files
		copts[defs.FROM_PARS] = True

	elif copts["cmd"] == defs.COPY_FILE:
		if len( copts["params"] ) != 2 or \
			len( copts["params"][0] ) == 0 or len( copts["params"][1] ) == 0:
			print( "'cp' command requires two parameters." )
			return 1
		src = copts["params"][0]
		dst = copts["params"][1]
		writeFile = None
		if src[0] == ':':
			if copts["server_side"]:
				print( "Destination file cannot be on server side." )
				return 1
			else:
				writeFile = dst
		if dst[0] == ':' and not copts["server_side"]:
			if not os.path.exists( src ):
				print( "File not found: ", src )
				return 1
			with open( src ) as f:
				copts["params"][0] = f.read()

			copts[defs.FROM_PARS] = True

	copts.pop( defs.SERVER_SIDE, None )

	if not copts:
		copts = None

	res, ret = Client( copts, sockfile, host, port )

	# Postprocessing

	if res:
		if copts["cmd"] == defs.COPY_FILE:
			if writeFile:
				try:
					with open( writeFile, "w" ) as f:
						f.write( ret )
				except Exception:
					print( "0Error: Failed storing query result to file '{0}'".format( writeFile ) )
					return -1

	return res, ret

def main( *kwargs ):
	'''main()'''
	# pylint: disable=too-many-branches,too-many-statements,

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

	cmdoptions = defaultdict( list )

	class CmdParam( argparse.Action ):
		def __call__( self, parser, namespace, values, option_string = None ):
			if not values:
				raise ValueError( "Command parameter must have a value" )
			cmdoptions[declc( self.dest )].append( values )

	class CmdSwitch( argparse.Action ):
		def __call__( self, parser, namespace, values = None, option_string = None ):
			if values:
				raise ValueError( "Command switch cannot have values" )
			cmdoptions[declc( self.dest )] = True

	parser = argparse.ArgumentParser( 
		description = 'regd : Data cache server.'
	)

	parser.add_argument( 'cmd', choices = [clc( x ) for x in defs.all_cmds], help = 'Regd command' )
	parser.add_argument( 'params', nargs = "*", help = 'Command parameters' )

	# Regd options
	parser.add_argument( clp( defs.LOG_LEVEL ), default = 'WARNING', help = 'DEBUG, INFO, WARNING, ERROR, CRITICAL' )
	parser.add_argument( clp( defs.LOG_TOPICS ), help = 'For debugging purposes.' )
	parser.add_argument( clp( defs.SERVER_NAME ), help = 'The name of the server instance.' )
	parser.add_argument( clp( defs.HOST ), help = 'Run the server on an Internet socket with the specified hostname.' )
	parser.add_argument( clp( defs.PORT ), help = 'Run the server on an Internet socket with the specified port.' )
	parser.add_argument( clp( defs.ACCESS ), help = 'Access level for the server: secure, private, public_read or public.' )
	parser.add_argument( clp( defs.DATAFILE ), help = 'File for reading and storing persistent tokens.' )
	parser.add_argument( clp( defs.NO_VERBOSE ), action = 'store_true', help = 'Only output return code numbers.' )
	parser.add_argument( clp( defs.AUTO_START ), action = 'store_true', help = 'If regd server is not running, start it before executing the command.' )

	# Command options
	parser.add_argument( clp( defs.DEST ), "-d", action = CmdParam, help = "The name of the section into which tokens must be added." )
	parser.add_argument( clp( defs.TREE ), "-t", action = CmdSwitch, nargs = 0, help = "Output the sections' contents in tree format." )
	parser.add_argument( clp( defs.PERS ), action = CmdSwitch, nargs = 0, help = "Apply the command to persistent tokens." )
	parser.add_argument( clp( defs.FORCE ), "-f", action = CmdSwitch, nargs = 0, help = "Overwrite existing token values when adding tokens." )
	parser.add_argument( clp( defs.SERVER_SIDE ), action = CmdSwitch, nargs = 0, help = "Execute command on the server side (only for 'client-or-server' commands)." )
	parser.add_argument( clp( defs.BINARY ), "-b", action = CmdParam, help = "Binary data." )
	parser.add_argument( clp( defs.ATTRS ), "-a", action = CmdParam, help = "Token attributes." )
	parser.add_argument( clp( defs.RECURS ), "-r", action = CmdSwitch, nargs = 0, help = "Apply the command recursively." )
	parser.add_argument( clp( defs.SUM ), action = CmdSwitch, nargs = 0, help = "Sum up the token with the existing value." )

	args = parser.parse_args( *kwargs )

	cmd = declc( args.cmd )

	cmdoptions["cmd"] = cmd
	cmdoptions["params"] = args.params

	if cmd == defs.HELP:
		print( USAGE )
		return 0

	# Setting up logging

	util.setLog( args.log_level, args.log_topics )
	log = util.log

	log.debug( vars( args ) )

	# Setting up server name

	try:
		atuser, servername = util.parse_server_name( args.server_name )
	except IKException as e:
		print( e )
		return e.code
	log.debug( "Server name: %s ; atuser: %s" % ( servername, atuser ) )

	if servername == "regd":
		raise  IKException( ErrorCode.unrecognizedParameter,
			"Default server name should not be specified in command line parameters." )
	if not servername:
		servername = "regd"

	userid = os.getuid()
	app.homedir = app.get_home_dir()
	app.confdir = app.get_conf_dir()

	log.debug( "userid: %i ; homedir: %s ; confdir: %s  ", userid, app.homedir, app.confdir )

	d = {}
	app.read_conf( d )

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
		log.debug( "sockdir: %s ; sockfile: %s  " % ( sockdir, _sockfile ) )
	else:
		sockdir, _sockfile = util.get_filesock_addr( None, host + '_' + port )
		_sockfile += ".ip"
		log.debug( "host: %s ; port: %s  " % ( host, port ) )

	# File log
	if "logfile" in d:
		logfile = d["logfile"]
		if not os.path.isfile( logfile ):

			with open( logfile, 'w' ) as f:
				f.write( "" )

		filelog = logging.FileHandler( logfile )
		filelog.setLevel( logging.INFO )
		bf = logging.Formatter( "[{asctime:s}] {module:s} {levelname:s} {funcName:s} : {message:s}", "%m-%d %H:%M", "{" )
		filelog.setFormatter( bf )
		util.log.addHandler( filelog )

	# Test module
	tstdir = os.path.dirname( os.path.realpath( __file__ ) ) + "/testing"
	# tst = tstdir + "/tests.py"

	# Test helper module.
	tsthelp = tstdir + "/test_help.py"

	# Handling command line

	# Server commands

	if args.auto_start:
		raise Exception("No autostart")
		if not checkConnection( _sockfile, host, port ):
			opts = [__file__, defs.START_SERVER]
			if host:
				opts.append( "--host" );
				opts.append( host )
			if port:
				opts.append( "--port" );
				opts.append( port )
			if args.server_name:
				opts.append( "--server-name" );
				opts.append( args.server_name )
			if args.access:
				opts.append( "--access" );
				opts.append( args.access )
			if args.datafile:
				opts.append( "--datafile" );
				opts.append( args.datafile )
			if args.log_level:
				opts.append( "--log-level" );
				opts.append( args.log_level )
			log.info( "The server isn't running. Autostarting with arguments:%s" % ( str( opts ) ) )
			subprocess.Popen( opts )
			time.sleep( 2 )

	if cmd == defs.START_SERVER:
		# Setting up start configuration

		if atuser and userid:
			log.error( "Server cannot be started with server name containing '@'." )
			return 1

		try:
			os.makedirs( sockdir, mode = 0o777, exist_ok = True )
			os.chmod( sockdir, mode = 0o777 )
		except Exception as e:
			print( "Error: cannot create temporary file socket directory. Exiting." )
			return -1

		# Permission level

		if args.access:
			if args.access.startswith("0o"):
				acc = int( args.access, 8 )
			elif args.access == "secure":
				acc = defs.PL_SECURE
			elif args.access == "private":
				acc = defs.PL_PRIVATE
			elif args.access == "public-read":
				acc = defs.PL_PUBLIC_READ
			elif args.access == "public":
				acc = defs.PL_PUBLIC
			else:
				print( "Unknown access mode. Must be: 'secure', 'private', 'public-read' or 'public'" )
				return 1
		else:
			acc = defs.PL_PRIVATE
			args.access = acc
		log.debug( "Permission level: %s" % args.access )

		# Data file

		# Default data directory
		DATADIR = app.confdir + "/data/"

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
			if acc == defs.PL_SECURE:
				print( "Secure access and --datafile option cannot be both specified")
				return 1

			if datafile == "None":
				datafile = None
			else:
				if not os.path.exists( datafile ):
					print( "Error: data file doesn't exist: \"{0}\".".format( datafile ),
						"Server is not started." )
					return -1
		elif DATADIR and acc != defs.PL_SECURE:
			# Composing the default data file name
			if host:
				datafile = host + "." + port + ".data"
			else:
				datafile = servername + ".data"

			datafile = DATADIR + datafile
			if not os.path.exists( datafile ):
				fp = open( datafile, "w" )
				fp.write( "" )
				fp.close()

		log.debug( "datafile: %s" % datafile )
		
		# bin_section file
		binsect = d.get( "bin_section", None )
		if not binsect:
			if os.path.isfile( os.path.join( DATADIR, "bin_section") ):
				binsect = os.path.join( DATADIR, "bin_section" )

		log.info( "Starting server %s : %s, access: %s " % (( servername, host )[bool( host )], 
								( _sockfile, port )[bool( host )], args.access ) )
		return rgs.startRegistry( servername, _sockfile, host, port, acc, datafile, binsect )

	elif cmd == defs.STOP_SERVER:
		res, _ = Client( { "cmd": defs.STOP_SERVER }, _sockfile, host, port )
		if not res:
			if not args.no_verbose:
				util.log.error( "cmd 'stop': Cannot contact server." )
			return -1

	elif cmd == defs.RESTART_SERVER:
		bresAcc, retAcc = Client( { "cmd": defs.REPORT, "params":[defs.ACCESS] }, _sockfile, host, port )
		bresDf, retDf = Client( { "cmd": defs.REPORT, "params":[defs.DATAFILE] }, _sockfile, host, port )
		bres, _ = Client( { "cmd": defs.STOP_SERVER }, _sockfile, host, port )
		if not bres:
			log.error( "cmd 'restart': Cannot contact server." )
			return -1

		if not bresAcc:
			print( "Error: Could not get the permission level of the current server instance.",
				"Server has been stopped and not restarted." )
			return -1
		if not bresDf:
			print( "Error: Could not get the data file name of the current server instance.",
				"Server has been stopped and not restarted." )
			return -1

		time.sleep( 3 )

		return rgs.startRegistry( servername, _sockfile, host, port, int( retAcc ), retDf )

	elif isServerCmd( cmdoptions ):
		res, ret = doServerCmd( cmdoptions, _sockfile, host, port )

		# Postprocessing

		if not res:
			if ret[0] != '0':
				print( "0", ret )
			else:
				print( ret )
			return -1

		print( '1' )
		if ret:
			util.printObject( ret )

	# Local commands

	elif cmd == defs.SHOW_LOG:
		with open( logfile, "r" ) as f:
			ls = f.readlines()[-int( args.show_log ):]
			[print( x.strip( '\n' ) ) for x in ls ]

	elif cmd == defs.VERS:
		print( "Regd version on client: " + defs.__version__ )

	elif cmd == defs.TEST_CONFIGURE:
		subprocess.call( ["python", tsthelp, "--test-configure"] )

	elif cmd == defs.TEST_START:
		print( "\nIt's recommended to shutdown all regd server instances before testing." )
		ans = input( "\nPress 'Enter' to begin test, or 'q' to quit." )
		if ans and ans in 'Qq':
			return 0
		print( "Setting up test, please wait..." )
		subprocess.call( ["python", "-m", "unittest", "regd.testing.tests.currentTest"] )

	elif cmd == defs.TEST_MULTIUSER_BEGIN:
		subprocess.Popen( [tsthelp, "--test-multiuser-begin"] )

	elif cmd == defs.TEST_MULTIUSER_END:
		subprocess.Popen( [tsthelp, "--test-multiuser-end"] )


	return 0


if __name__ == "__main__":
	sys.exit( main( sys.argv[1:] ) )
