'''*******************************************************************
*	Module:			regd.serv
*
*	Created:		Jul 5, 2015
*
*	Abstract:		Server.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*
********************************************************************'''
__lastedited__ = "2016-05-24 13:18:57"

import sys, time, subprocess, os, pwd, signal, socket, struct, datetime, selectors
import multiprocessing as mp
from threading import Thread
import ipaddress, shutil
import regd.defs as defs
import regd.util as util
from regd.util import log, composeResponse
from regd.appsm.app import IKException, ErrorCode, ROAttr
import regd.stor as stor
import regd.appsm.app as app
import regd.tok as modtok
from regd.cmds import CmdSwitcher, CmdProcessor
import regd.info as info

srv = None

SRV_INFO = "SRV_INFO"

class RegdServer( CmdProcessor ):
	'''Regd server.'''

	cmdDefs = ( ( defs.STOP_SERVER, "0", None, {defs.NO_VERBOSE}, "chStopServer" ), 
				( SRV_INFO, "?", None, None, "chSrvInfo" ) 
			)

	
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
		self.sigsock_r = None
		self.sigsock_w = None
		self.sel = None
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

		info.setShared( "accLevel","{0} ({1})".format( defs.PL_NAMES[self.acc], oct(self.acc) ) )
		info.setShared( "sockFile", self.sockfile )

	def __del__( self ):
		# close() is better to be called earlier in order for closing routines not be
		# called when some modules are unloaded
		self.close()

	def close( self ):
		'''Dispose.'''
		log.debug("Closing...")
		if self.disposed:
			log.debug("Already closed.")
			return
		self.disposed = True
		if os.path.exists( str( self.sockfile ) ):
			log.info( "Stopping server: unlinking socket file..." )
			os.unlink( self.sockfile )
		log.debug("Closed OK.")

	def start_loop( self, sigStor ):
		'''Start loop.'''

		# Check for the previous instance

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
		
		# Set up sockets
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

		self.sock.listen( 1 )
		self.sock.settimeout( 30 )
		self.sel = selectors.DefaultSelector()
		self.sigsock_r, self.sigsock_w = socket.socketpair()
		self.sigsock_r.setblocking( False )
		self.sigsock_w.setblocking( False )
		os.set_inheritable( self.sigsock_w.fileno(), True )
		self.sock.setblocking( False )
		signal.set_wakeup_fd( self.sigsock_w.fileno() )
		self.sel.register( self.sock, selectors.EVENT_READ, self.accept )
		self.sel.register( self.sigsock_r, selectors.EVENT_READ, self.stop )
		self.sel.register( sigStor, selectors.EVENT_READ, self.stop )
		self.loop( self.sock, )

	def loop( self, sock ):
		self.cont = True
		self.exitcode = 0

		while app.glCont:
			events = self.sel.select( 30 )
			for key, mask in events:
				callback = key.data
				callback(key.fileobj, mask)
			
			if not os.path.exists( self.sockfile ):
				log.error( "Socket file {0} is gone. Exiting.".format( self.sockfile ) )
			else:
				continue
								
	def accept(self, sock, mask):
		try:
			connection, client_address = sock.accept()
		except Exception as e:
			log.error( "Exception occured: ", e )
			return

		mp.Process( target = self.handle_connection, name = "RegdConnectionHandler",
							args = ( connection, client_address, util.connLock ) ).start()
							
	def stop(self, sock, mask):
		'''Regd stop handler. The program is normally stopped only through this.
		It's called when the sigsocket receives input ( including notification 
		about a signal ). '''
		log.info("Stopping server...")
		if app.glCont:
			app.glCont = False
			app.glSignal.acquire()
			app.glSignal.notify()
			app.glSignal.release()
		self.close()
			
	def chSrvInfo( self, cmd ):
		path = cmd.get("params")
		if not path:
			return util.printMap( self.info, 0 )
		else:
			path = path[0]
			item = self.getItem( path )
			m = item.stat()
			return util.printMap( m, 0 )

	def handle_connection( self, *args ):
		'''Exceptions-catcher wrapper'''
		connection = args[0]
		client_address = args[1]
		storage_lock = args[2]
		try:
			self._handle_connection( connection, client_address, storage_lock )
		except IKException as e:
			log.error( ( "Exception while handling connection. Continuing loop."
						"Client: %s ; Exception: %s" ) % ( client_address, e ) )

		except Exception as e:
			log.error( "Exception in server loop. Exiting. %s" % ( e ) )
			self.sigsock_w.send("stop".encode())

		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()

	def _handle_connection( self, connection, client_address, storage_lock ):
		'''Connection handler'''
		if not self.host:
			creds = connection.getsockopt( socket.SOL_SOCKET, socket.SO_PEERCRED,
									struct.calcsize( "3i" ) )
			pid, uid, gid = struct.unpack( "3i", creds )
			log.debug( "new connection: pid: {0}; uid: {1}; gid: {2}".format( pid, uid, gid ) )
		else:
			log.debug( "new connection: client address: %s" % ( str( client_address ) ) )

		connection.settimeout( 5 )

		data = bytearray()
		util.recvPack( connection, data )
		bytesReceived = len( data )

		log.debug( "data: %s" % ( data[:1000] ) )
		data = data[10:]  # .decode( 'utf-8' )

		bresp = bytearray()
		cmd = None
		perm = False
		# dcmd - command dictionary. Contains three fields:
		# cmd - command name, received from client
		# params - command parameters, received from client
		# res - internal command processing result, set by the command processor or
		# command handler. This result has the server semantics, rather than the
		# command semantics: if it's 0 - this means a general program error, e.g.
		# non-existing command name. It's meant to be handled by the server before
		# sending response to the client.
		
		try:
			dcmd = util.parsePacket( data )
			# 'internal' switch is only used within regd server
			if "internal" in dcmd:
				raise Exception("Unrecognized syntax.")
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
			util.connLock = storage_lock
			bresp = CmdSwitcher.handleCmd( dcmd )

		try:
			bytesSent = util.sendPack( connection, bresp )
		except OSError as er:
			log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
							er.errno, er.strerror, client_address ) )
		else:
			info.setShared( "bytesReceived", bytesReceived, defs.SUM )
			info.setShared( "bytesSent", bytesSent, defs.SUM )

		if cmd == defs.STOP_SERVER and perm:
			self.sigsock_w.send("stop".encode())

		return

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
		log.debug("In chStopServer")
		return composeResponse( '1', "Exiting..." )

