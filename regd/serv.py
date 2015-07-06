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
__lastedited__="2015-07-06 04:30:46"

import sys, time, subprocess, os, pwd, signal, socket, struct, datetime
import ipaddress
import fcntl  # @UnresolvedImport
import regd.util as util, regd.defs as defs
from regd.util import log, ISException, permissionDenied, persistentNotEnabled, valueNotExists,\
	operationFailed, getcp, sigHandler, clientConnectionError, unknownDataFormat
from regd.stor import read_locked, list_tokens, add_token, write_locked, get_token,\
	read_sec_file, remove_section, remove_token
import __main__  # @UnresolvedImport
from regd.defs import *  # @UnusedWildImport

class RegdServer:
	def __init__(self, servername, sockfile, host, port, acc, datafile ):
		self.servername = servername
		self.sockfile = sockfile
		self.host = host
		self.port = port
		self.acc = acc
		self.datafile = datafile
		self.data_fd = None
		
		self.stat = {}
		self.stat["general"]={}
		self.stat["tokens"]={}
		self.stat["commands"]={}
		self.mcmd = self.stat["commands"]
		self.tokens = util.getcp()
		self.sectokens = util.getcp()
		self.perstokens = util.getcp()
		self.timestarted = None
		self.useruid = None
			
		# Default encrypted file name
		self.encFile = defs.homedir + "/.sec/safestor.gpg"
		# Flag showing whether the default enc. file has been read
		self.defencread = False
		# Command line command for reading encrypted file
		self.secTokCmd = defs.READ_ENCFILE_CMD
		
		self.itemsSep = defs.ITEMMARKER 
		
		# Trusted
		self.trustedUserids = []
		self.trustedIps = []
	
		d = {}
		util.read_conf( d )
		if "encfile" in d:
			self.encFile = d["encfile"]
		if "token_separator" in d:
			self.itemsSep = d["token_separator"]
		if "encfile_read_cmd" in d:
			self.secTokCmd = d["encfile_read_cmd"]
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
					self.trustedIps.append(ipaddr)
		elif not host and "trusted_users" in d:
			trustedNames = d["trusted_users"]
			if trustedNames:
				trustedNames = trustedNames.split(' ')
				for un in trustedNames:
					try:
						uid = pwd.getpwnam( un ).pw_uid
					except:
						continue
					self.trustedUserids.append(uid)
					
		if self.datafile:
			# Obtaining the lock
			try:
				self.data_fd = open( self.datafile, "r+", buffering=1 )
				log.debug("Data file fileno: %i" % (self.data_fd.fileno()))
				fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB )
			except OSError as e:
				print("Error: data file \"{0}\" could not be opened: {1}".format(datafile, e.strerror), 
				"Probably it's already opened by another process. Server is not started.")
				return -1
		else:
			print( "Server's data file is not specified. Persistent tokens are not enabled.")
			
		if self.data_fd:
			try:
				read_locked( self.data_fd, self.perstokens, True )
			except ISException as e:
				log.error( "Cannot read the data file: %s" % ( str(e)))
				return -1
			
		def signal_handler( signal, frame ):
			if os.path.exists(sockfile):
				log.info("Signal is received. Unlinking socket file...")
				os.unlink( sockfile )
			sys.exit( 1 )
			
		sigHandler.push(signal.SIGINT, signal_handler)
		sigHandler.push(signal.SIGTERM, signal_handler)
		sigHandler.push(signal.SIGHUP, signal_handler)
		sigHandler.push(signal.SIGABRT, signal_handler)
		
	def start_loop(self):
		
		if self.sockfile and os.path.exists( self.sockfile ):
			'''Socket file may remain after an unclean exit. Check if another server is running.'''
			try:
				# If the server is restarted, give the previous instance time to exit cleanly.
				time.sleep( 2 )
				res = subprocess.check_output( 
							"ps -ef | grep '{0} --start .* {1} ' | grep -v grep".format( 
												__main__.__file__, self.servername ),
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
				os.unlink( self.sockfile )
			except OSError:
				if os.path.exists( self.sockfile ):
					raise	
				
		log.info( "Starting server..." )
		self.useruid = os.getuid()
		self.stat["general"]["time_started"] = str(datetime.datetime.now()).rpartition(".")[0] 
		self.timestarted = datetime.datetime.now()
		try:
			if self.host:
				sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
				sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
				sock.bind( ( self.host, int(self.port) ) )
			else:
				sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
				sock.bind( self.sockfile )
				os.chmod( self.sockfile, mode=0o777 )
				
		except OSError as e:
			log.error( "Cannot create or bind socket: %s" % (e) )
			return -1
	
		sock.listen( 1 )
		self.loop(sock)
	

	def loop(self, sock):
		while True:
			connection, client_address = sock.accept()
			try:
				cont = self.handle_connection(connection, client_address)
			except ISException as e:
				log.error( ( "Exception while handling connection. Continuing loop." 
							"Client: %s ; Exception: %s") % (client_address, e))				
			except Exception as e:
				log.error("Exception in server loop. Exiting. %s" % (e))
				sys.exit(-1)
			finally:
				connection.shutdown( socket.SHUT_RDWR )
				connection.close()
			if not cont:
				log.info("Server exiting.")
				sys.exit( 0 )		
		
	def handle_connection(self, connection, client_address):	
		if not self.host:
			creds = connection.getsockopt( socket.SOL_SOCKET, socket.SO_PEERCRED, 
									struct.calcsize("3i"))
			pid, uid, gid = struct.unpack("3i", creds)
			log.info("new connection: pid: {0}; uid: {1}; gid: {2}".format( pid, uid, gid ) )
		else:
			log.info( "new connection: client address: %s" % ( str( client_address ) ) )

		connection.settimeout( 3 )
		itemmarksize = len( self.itemsSep )
		
		data = bytearray()
		util.recvPack(connection, data)
		
		log.debug("data: %s" % (data[:1000]))
		data = data[10:].decode( 'utf-8' )
		
		# Server commands and regd command line commands and options are two different sets:
		# the latter is the CL user interface, and the former is the internal communication 
		# protocol.
		# Regd client receives commands from the command line, converts it to server command 
		# syntax, and sends it in the form of command packet to the server.
		# Each packet contains exactly one command and related to it options, if any.
		# Format of command packets:
		# <COMMAND> <DATALENGTH> [DATA] [OPTION DATALENGTH DATA]...
		cmdOptions = []
		cmd = None
		cmdData = None 
		while data:
			word, _, data = data.partition(' ')
			if not data:
				raise ISException(unknownDataFormat)
			datalen, _, data = data.partition(' ')
			try:
				datalen = int( datalen )
				if not (datalen <= len( data )): raise
				if datalen: 
					worddata = data[:datalen]
					data = data[datalen+1:]
				else:
					worddata = None
					
				if word in defs.all_cmds:
					# One command per packet
					if cmd: raise 
					cmd = word
					cmdData = worddata
				elif word in defs.cmd_options:
					cmdOptions.append(( word, worddata ))
				else:
					raise 
			except:
				raise ISException(unknownDataFormat)
			
		if not cmd:
			raise ISException(unknownDataFormat)
			
		log.info( "command received: {0}".format( cmd ) )

		# Three response classes:
		# 0 - program error
		# 1 - success
		# >1 - operation unsuccessful (e.g. key doesn't exist)
		resp = "0"
		perm = False
		
		if self.host:
			# IP-based server
			if not self.trustedIps:
				perm = True
			else :
				try:
					clientIp = ipaddress.IPv4Address(client_address[0])
				except ValueError:
					log.error("Client IP address format is not recognized.")
				else:
					for i in self.trustedIps:
						if clientIp in i:
							perm = True
							log.info("Client IP is trusted.")
							break 
					if not perm:
						log.error("Client IP is NOT trusted : '%s : %s" % 
								(client_address[0], client_address[1]))
		else:
			# File socket server
			if self.useruid == uid:
				perm = True
			elif uid in self.trustedUserids:
				perm = True
			elif cmd not in secure_cmds:
				if self.acc == PL_PUBLIC:
					perm = True
				elif self.acc == PL_PUBLIC_READ:
					if cmd in pubread_cmds:
						perm = True 

		if not perm:
			resp = str( ISException( permissionDenied, cmd ) )
		elif not self.data_fd and cmd in pers_cmds:
			resp = str( ISException(persistentNotEnabled))
		else:
			self.mcmd[cmd] = 1 if cmd not in self.mcmd else self.mcmd[cmd]+1
			
			if cmd == STOP_SERVER:
				resp = "1"

			if cmd == CHECK_SERVER:
				resp = "1Up and running since {0}\nUptime:{1}.".format(	
						str(self.timestarted).rpartition(".")[0], 
						str(datetime.datetime.now() - self.timestarted).rpartition(".")[0])
			
			if cmd == REPORT:
				if len( cmdOptions ) != 1:
					resp = "0Unrecognized command syntax"
				else:
					if cmdOptions[0][0] == defs.ACCESS:
						resp = "1{0}".format( self.acc )
					elif cmdOptions[0][0] == defs.STAT:
						resp = "1" + self.prepareStat()
					elif cmdOptions[0][0] == defs.DATAFILE:
						resp = "1" + self.datafile
					else:
						resp = "0Unrecognized command syntax"
			if cmd == LIST:
				if not len( cmdData ): cmdData = "/"
				s = ""
				if cmdData.startswith("/ses") or cmdData == "/":
					s = list_tokens(self.tokens, cmdData, tree)
				
			if cmd == LIST_TOKENS_PERS:
				sects = cmdData.split( "," ) if len( cmdData ) else None
				try:
					resp = "1" + list_tokens( self.perstokens, sects )
				except ISException as e:
					resp = str( e )

			if cmd == LIST_TOKENS_SESSION:
				sects = cmdData.split( "," ) if len( cmdData ) else None
				try:
					resp = "1" + list_tokens( self.tokens, sects )
				except ISException as e:
					resp = str( e )

			if cmd == LIST_TOKENS_ALL:
				try:
					s = list_tokens( self.tokens )
					if self.data_fd:
						s += list_tokens( self.perstokens )
					resp = "1" + s
				except ISException as e:
					resp = str( e )

			elif cmd == ADD_TOKEN:
				'''Strict add: fails if the token already exists.'''
				try:
					add_token( self.tokens, cmdData, noOverwrite = True )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == SET_TOKEN:
				try:
					add_token( self.tokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == ADD_TOKEN_PERS:
				'''Strict add: fails if the token already exists.'''
				try:
					add_token( self.perstokens, cmdData, noOverwrite = True )
					write_locked( self.data_fd, self.perstokens )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == SET_TOKEN_PERS:
				try:
					add_token( self.perstokens, cmdData )
					write_locked( self.data_fd, self.perstokens )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == LOAD_TOKENS:
				try:
					pl = cmdData.find( self.itemsSep )
					while pl != -1:
						newitem = cmdData[:pl]
						add_token( self.tokens, newitem )
						cmdData = cmdData[( pl + itemmarksize ):]

					add_token( self.tokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == LOAD_TOKENS_PERS:
				try:
					pl = cmdData.find( self.itemsSep )
					while pl != -1:
						newitem = cmdData[:pl]
						add_token( self.perstokens, newitem )
						cmdData = cmdData[( pl + itemmarksize ):]

					add_token( self.perstokens, cmdData )
					write_locked( self.data_fd, self.perstokens )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == GET_TOKEN:
				'''Get a token. '''
				try:
					resp = "1" + get_token( self.tokens, cmdData )
				except ISException as e:
					resp = str( e )

			elif cmd == GET_TOKEN_PERS:
				'''Get a persistent token. '''
				try:
					resp = "1" + get_token( self.perstokens, cmdData )
				except ISException as e:
					resp = str( e )

			elif cmd == GET_TOKEN_SEC:
				''' Get secure token. '''
				if not len( cmdData ):
					resp = "0No token specified."
				else:
					try:
						if not self.sectokens():
							'''Sec tokens are not read yet. Read the default priv. file.'''
							if not self.defencread:
								read_sec_file( self.encFile, self.secTokCmd, self.sectokens )
								self.defencread = True
						resp = "1" + get_token( self.sectokens, cmdData )
					except ISException as e:
						resp = str( e )

			elif cmd == LOAD_FILE:
				'''Load tokens from a file.'''
				try:
					if os.path.exists( cmdData ):
						self.tokens.read( cmdData )
						resp = "1"
					else:
						resp = "{0}File not found: {1}".format( valueNotExists, cmdData )
				except OSError as e:
					resp = "{0}Cannot read the file: {1}".format( operationFailed, e.strerror )

			elif cmd == LOAD_FILE_PERS:
				'''Add persistent tokens from a file.'''
				try:
					if os.path.exists( cmdData ):
						read_locked( self.data_fd, self.perstokens, False)
						write_locked( self.data_fd, self.perstokens )
						resp = "1"
					else:
						resp = "{0}File not found: {1}".format( valueNotExists, cmdData )
				except OSError as e:
					resp = "{0}Cannot read the file: {1}".format( operationFailed, e.strerror )

			elif cmd == LOAD_FILE_SEC:
				if not len( cmdData ):
					file = self.encFile
				else:
					file = cmdData

				try:
					read_sec_file( file, self.secTokCmd, self.sectokens  )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == REMOVE_TOKEN:
				try:
					remove_token( self.tokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == REMOVE_SECTION:
				try:
					remove_section( self.tokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == REMOVE_TOKEN_PERS:
				try:
					remove_token( self.perstokens, cmdData )
					write_locked( self.data_fd, self.perstokens )
					resp = "1"
				except ISException as e:
					resp = str( e )

			elif cmd == REMOVE_SECTION_PERS:
				try:
					remove_section( self.perstokens, cmdData )
					write_locked( self.data_fd, self.perstokens )
					resp = "1"
				except ISException as e:
					resp = str( e )
					
			elif cmd == REMOVE_TOKEN_SEC:
				try:
					remove_token( self.sectokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )
					
			elif cmd == REMOVE_SECTION_SEC:
				try:
					remove_section( self.sectokens, cmdData )
					resp = "1"
				except ISException as e:
					resp = str( e )
					
			elif cmd == CLEAR_SEC:
				self.sectokens = getcp()
				resp = "1"

			elif cmd == CLEAR_SESSION:
				self.sectokens = getcp()
				self.tokens = getcp()
				resp = "1"
					
		try:
			util.sendPack(connection, bytearray( resp, encoding = 'utf-8' ) )
		except OSError as er:
			log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
							er.errno, er.strerror, client_address ) )

		if cmd == STOP_SERVER and perm:
			log.info( "Stopping server." )
			if self.sockfile:
				os.unlink( self.sockfile )
			return False
		
		return True
		
	def prepareStat(self):
		ret = ""
		m = util.statReg( self.tokens )
		ret += ( "\nSession tokens:\n------------------------\n")
		ret += util.printMap( m, 0 )
		m = util.statReg( self.perstokens )
		ret += ( "\nPersistent tokens:\n------------------------\n")
		ret += util.printMap( m, 0 )
		ret += ( "\nCommands:\n------------------------\n")
		ret += util.printMap( self.mcmd, 0 )
		return ret		

def Server( servername, sockfile=None, host=None, port=None, acc=defs.PL_PRIVATE, datafile=None ):
	RegdServer( servername, sockfile, host, port, acc, datafile ).start_loop()
	
	
