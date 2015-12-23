'''
/********************************************************************
*	Module:			regd.serv
*
*	Created:		Jul 5, 2015
*
*	Abstract:		Server.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*
*********************************************************************/
'''
__lastedited__ = "2015-12-23 00:19:53"

import sys, time, subprocess, os, pwd, signal, socket, struct, datetime
from threading import Thread
import ipaddress, shutil
import regd.defs as defs
import regd.util as util
from regd.util import log, composeResponse
from regd.app import IKException, ErrorCode, ROAttr
import regd.stor as stor
import regd.app as app
import regd.tok as modtok
from regd.cmds import CmdSwitcher, CmdProcessor

srv = None


class RegdServer( CmdProcessor ):
	'''Regd server.'''

	cmdDefs = ( ( defs.STOP_SERVER, "0", None, {defs.NO_VERBOSE}, "chStopServer" ), )
	
	# Read-only fields
	servername 	= ROAttr( "servername", str() )
	sockfile 	= ROAttr( "sockfile", str() )
	host 		= ROAttr( "host", str() )
	port 		= ROAttr( "port", str() )
	acc 		= ROAttr( "acc", int() )

	def __init__( self, servername, sockfile, host, port, acc ):
		super( RegdServer, self).__init__()
		self.servername = servername
		self.sockfile = sockfile
		self.host = host
		self.port = port
		self.acc = acc
		self.sock = None
		self.info = {}
		self.disposed = False

		# Trusted
		self.trustedUserids = []
		self.trustedIps = []

		d = {}
		app.read_conf( d )
		if host and "trusted_ips" in d:
			ips = d["trusted_ips"]
			if ips:
				ips = ips.split( ' ' )
				for ip in ips:
					try:
						ipaddr = ipaddress.IPv4Network( ip )
					except ValueError:
						log.warning( "Trusted IPv4 %s is not a valid IP mask." % ( ip ) )
						continue
					self.trustedIps.append( ipaddr )
		elif not host and "trusted_users" in d:
			trustedNames = d["trusted_users"]
			if trustedNames:
				trustedNames = trustedNames.split( ' ' )
				for un in trustedNames:
					try:
						uid = pwd.getpwnam( un ).pw_uid
					except:
						continue
					self.trustedUserids.append( uid )
					
		RegdServer.registerGroupHandlers( self.processCmd )


	def __del__( self ):
		# close() is better to be called earlier in order for closing routines not be
		# called when some modules are unloaded
		self.close()

	def close( self ):
		'''Dispose.'''
		if self.disposed:
			return
		self.disposed = True
		self.serialize()
		if os.path.exists( str( self.sockfile ) ):
			log.info( "Signal is received. Unlinking socket file..." )
			os.unlink( self.sockfile )

	def start_loop( self ):
		'''Start loop.'''	
		if not self.host and os.path.exists( self.sockfile ):
			log.info( "Socket file for a server with name already exists. Checking for the server process." )
			'''Socket file may remain after an unclean exit. Check if another server is running.'''
			try:
				# If the server is restarted, give the previous instance time to exit cleanly.
				time.sleep( 2 )
				if self.servername and self.servername != "regd":
					s = "ps -ef | grep '{0}(/cli.py)? start .*{1} {2}' | grep -v grep".format( 
												app.APPNAME,
												app.clp( defs.SERVER_NAME ),
												self.servername )
				else:
					s = "ps -ef | grep -E '{0}(/cli.py)? start' | grep -v '{1}' | grep -v grep".format( 
												app.APPNAME,
												app.clc( defs.SERVER_NAME ) )


				res = subprocess.check_output( s, shell = True ).decode( 'utf-8' )

			except subprocess.CalledProcessError as e:
				if e.returncode != 1:
					log.error( "Check for already running server instance failed: {0} ".format( e.output ) )
					return -1
				else:
					res = ""

			if len( res ):
				# TODO
				if res.count( "\n" ) > 2:
					'''Server is already running.'''
					log.warning( "Server is already running:\n{0}".format( res ) )
					return 1
			log.info( "Server process is not found. Unlinking the existing socket file." )
			try:
				os.unlink( self.sockfile )
			except OSError:
				if os.path.exists( self.sockfile ):
					raise

		self.useruid = os.getuid()
		if self.host:
			log.info( "Starting regd server. useruid: {0} ; host: {1} ; port: {2}.".format( 
															self.useruid, self.host, self.port ) )
		else:
			log.info( "Starting regd server. useruid: {0} ; sockfile: {1} ; servername: {2}.".format( 
												self.useruid, self.sockfile, self.servername ) )
		self.info["time_started"] = str( datetime.datetime.now() ).rpartition( "." )[0]
		try:
			if self.host:
				self.sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
				self.sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
				self.sock.bind( ( self.host, int( self.port ) ) )
				with open( self.sockfile, "w" ) as f:
					f.write( '' )

			else:
				self.sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
				self.sock.bind( self.sockfile )
				os.chmod( self.sockfile, mode = 0o777 )

		except OSError as e:
			log.error( "Cannot create or bind socket: %s" % ( e ) )
			return -1

		self.sock.settimeout( 30 )
		self.sock.listen( 1 )
		Thread( target=self.loop, name="RegdServerLoop", args=( self.sock, ) ).start()

	def loop( self, sock ):
		self.cont = True
		self.exitcode = 0
		connection = None

		while True:
			try:
				connection, client_address = sock.accept()
			except socket.timeout:
				if not os.path.exists( self.sockfile ):
					log.error( "Socket file {0} is gone. Exiting.".format( self.sockfile ) )
					self.cont = False
					self.exitcode = 1
					connection = None
				else:
					continue

			except Exception as e:
				print( "Exception occured: ", e )
				connection = None
				self.cont = False

			if not self.cont:
				log.info( "Server exiting." )
				if connection:
					connection.shutdown( socket.SHUT_RDWR )
					connection.close()
				if self.sockfile:
					os.unlink( self.sockfile )
				sys.exit( self.exitcode )

			Thread( target = self.handle_connection, name = "handle_connection",
								args = ( connection, client_address ) ).start()

	def handle_connection( self, *args ):
		connection = args[0]
		client_address = args[1]
		try:
			self._handle_connection( connection, client_address )
		except IKException as e:
			log.error( ( "Exception while handling connection. Continuing loop."
						"Client: %s ; Exception: %s" ) % ( client_address, e ) )

		except Exception as e:
			log.error( "Exception in server loop. Exiting. %s" % ( e ) )
			self.cont = False
			self.exitcode = -1

		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()

	def _handle_connection( self, connection, client_address ):
		if not self.host:
			creds = connection.getsockopt( socket.SOL_SOCKET, socket.SO_PEERCRED,
									struct.calcsize( "3i" ) )
			pid, uid, gid = struct.unpack( "3i", creds )
			log.debug( "new connection: pid: {0}; uid: {1}; gid: {2}".format( pid, uid, gid ) )
		else:
			log.debug( "new connection: client address: %s" % ( str( client_address ) ) )

		connection.settimeout( 3 )

		data = bytearray()
		util.recvPack( connection, data )

		log.debug( "data: %s" % ( data[:1000] ) )
		data = data[10:]  # .decode( 'utf-8' )

		bresp = bytearray()
		cmd = None
		perm = False
		
		try:
			dcmd = util.parsePacket( data )
			cmd = dcmd["cmd"]
			log.debug( "command received: {0}".format( cmd ) )
		except Exception as e:
			bresp = composeResponse( "0", "Exception while parsing the command: " + str( e ) )
		else:
			# Check permission and persistency
			
			if self.host:
				# IP-based server
				if not self.trustedIps:
					perm = True
				else :
					try:
						clientIp = ipaddress.IPv4Address( client_address[0] )
					except ValueError:
						log.error( "Client IP address format is not recognized." )
					else:
						for i in self.trustedIps:
							if clientIp in i:
								perm = True
								log.debug( "Client IP is trusted." )
								break
						if not perm:
							log.error( "Client IP is NOT trusted : '%s : %s" %
									( client_address[0], client_address[1] ) )
			else:
				# File socket server
				if self.useruid == uid:
					perm = True
				elif uid in self.trustedUserids:
					perm = True
				elif cmd not in defs.secure_cmds:
					if self.acc == defs.PL_PUBLIC:
						perm = True
					elif self.acc == defs.PL_PUBLIC_READ:
						if cmd in defs.pubread_cmds:
							perm = True
			log.debug( "perm: {0}".format( perm ) )
			if not perm:
				bresp = composeResponse( "0", str( IKException( ErrorCode.permissionDenied, cmd ) ) )
			#elif not self.datafile and defs.PERS in cmd:
			#	bresp = composeResponse( "0", str( IKException( ErrorCode.operationFailed, None, "Persistent tokens are not enabled." ) ) )
		
		if not len( bresp ):
			try:
				bresp = CmdSwitcher.switchCmd( dcmd )
			except IKException as e:
				bresp = composeResponse( '0', str( e ) )
			except Exception as e:
				bresp = composeResponse( '0', e.args[0] )

		try:
			if not len( bresp ):
				bresp = composeResponse( "0", "Command not recognized" )
			util.sendPack( connection, bresp )
		except OSError as er:
			log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
							er.errno, er.strerror, client_address ) )

		if cmd == defs.STOP_SERVER and perm:
			app.glSignal.acquire()
			app.glSignal.notify()
			app.glSignal.release()

		return

	def serialize( self ):
		'''Serializing persistent tokens.'''
		if not stor.changed:
			return
		with stor.lock_changed:
			ch_ = stor.changed[:]
			stor.changed = []
		# Finding a common path separately for each serializable root
		for r in stor.serializable_roots:
			l = [x.pathName() for x in ch_ if x.pathName().startswith( r )]
			if not l:
				continue
			commonPath = os.path.commonpath( l )
			sec = self.fs.getItem( commonPath )
			fhd = {}
			sec.serialize( fhd, read = False )
			for fpath, fh in fhd.items():
				if fpath == "cur":
					continue
				fh.close()
				shutil.move( fpath, fpath[:-4] )
				
	def handleBinToken(self, dest, tok, optmap):
		if dest:
			tok = os.path.join( dest, tok )
		path, nam, val = modtok.parse_token( tok, bNam=True, bVal=True)
		sec = self.fs.getItem( path )
		exefile = sec.getItem( nam )
		log.debug( "Calling: " + exefile.val + " " + val )
		if tok.startswith(stor.BINPATH + "/sh/"):
			subprocess.call( exefile.val + " " + val, shell=True )
		else:
			subprocess.call( [exefile.val, val], shell=False )

	def chStopServer( self, cmd ):
		'''Stop regd server'''
		return composeResponse( '1', "Exiting..." )

