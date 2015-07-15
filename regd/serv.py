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
__lastedited__="2015-07-14 06:30:51"

import sys, time, subprocess, os, pwd, signal, socket, struct, datetime
import ipaddress
import fcntl  # @UnresolvedImport
import regd.util as util, regd.defs as defs
from regd.util import log, ISException, permissionDenied, persistentNotEnabled, valueNotExists,\
	operationFailed, sigHandler, unrecognizedParameter,\
	unrecognizedSyntax
from regd.stor import EnumMode, read_locked, write_locked, get_token,\
	read_sec_file, remove_section, remove_token, getstor
import regd.stor as stor
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
		self.tokens = getstor()
		self.sectokens = getstor()
		self.perstokens = getstor()
		self.fs = getstor()
		self.secfs = getstor()
		self.fs['']=getstor()
		self.fs[''][stor.SESNAME]=self.tokens
		self.fs[''][stor.PERSNAME]=self.perstokens
		self.secfs['']=getstor()
		self.secfs[''][stor.SESNAME]=self.tokens
		self.secfs[''][stor.PERSNAME]=self.perstokens
		self.timestarted = None
		self.useruid = None
			
		# Default encrypted file name
		self.encFile = defs.homedir + "/.sec/safestor.gpg"
		# Flag showing whether the default enc. file has been read
		self.defencread = False
		# Command line command for reading encrypted file
		self.secTokCmd = defs.READ_ENCFILE_CMD
		
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
				#fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB )
			except OSError as e:
				print("Error: data file \"{0}\" could not be opened: {1}".format(datafile, e.strerror), 
				"Server is not started.")
				raise ISException(operationFailed)
		else:
			print( "Server's data file is not specified. Persistent tokens are not enabled.")
			
		if self.data_fd:
			try:
				read_locked( self.data_fd, self.perstokens, True )
			except ISException as e:
				log.error( "Cannot read the data file: %s" % ( str(e)))
				raise ISException(operationFailed)
			
		def signal_handler( signal, frame ):
			if os.path.exists(sockfile):
				log.info("Signal is received. Unlinking socket file...")
				os.unlink( sockfile )
			if self.data_fd:
				fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_UN )
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
				
		self.useruid = os.getuid()
		if self.host:
			log.info( "Starting regd server. useruid: {0} ; host: {1} ; port: {2}.".format( 
															self.useruid, self.host, self.port )  )
		else:
			log.info( "Starting regd server. useruid: {0} ; sockfile: {1} ; servername: {2}.".format( 
												self.useruid, self.sockfile, self.servername )  )
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
			cont=True
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
				if self.data_fd:
					log.info("Unlocking data file.")
					fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_UN )
				sys.exit( 0 )		
		
	def handle_connection(self, connection, client_address):	
		if not self.host:
			creds = connection.getsockopt( socket.SOL_SOCKET, socket.SO_PEERCRED, 
									struct.calcsize("3i"))
			pid, uid, gid = struct.unpack("3i", creds)
			log.debug("new connection: pid: {0}; uid: {1}; gid: {2}".format( pid, uid, gid ) )
		else:
			log.debug( "new connection: client address: %s" % ( str( client_address ) ) )

		connection.settimeout( 3 )
		
		data = bytearray()
		util.recvPack(connection, data)
		
		log.debug("data: %s" % (data[:1000]))
		data = data[10:] #.decode( 'utf-8' )

		cmdOptions=[]
		cmdData=[]
		cmd = util.parsePacket(data, cmdOptions, cmdData)
			
		log.debug( "command received: {0} {1}".format( cmd, cmdData ) )
		log.debug( "command options: {0}".format( cmdOptions ) )

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
							log.debug("Client IP is trusted.")
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
		log.debug("perm: {0}".format( perm ) )
		if not perm:
			resp = str( ISException( permissionDenied, cmd ) )
		elif not self.data_fd and util.getSwitches(cmdOptions, PERS)[0]:
			resp = str( ISException(persistentNotEnabled))
		else:
			self.mcmd[cmd] = 1 if cmd not in self.mcmd else self.mcmd[cmd]+1
			
			# -------------- Command handling -----------------
			fpar = None
			if len( cmdData ):
				fpar = cmdData[0]
			spar = None
			if len( cmdData ) > 1:
				spar = cmdData[1] 
			
			log.debug("fpar: {0} ; spar: {1}".format( fpar, spar ) )
				
			try:
			
				if cmd == STOP_SERVER:
					resp = "1"
	
				elif cmd == CHECK_SERVER:
					resp = "1Up and running since {0}\nUptime:{1}.".format(	
							str(self.timestarted).rpartition(".")[0], 
							str(datetime.datetime.now() - self.timestarted).rpartition(".")[0])
					
				elif cmd == VERS:
					resp = "1 Regd version on server: " + defs.__version__
				
				elif cmd == REPORT:
					if not fpar:
						resp = "0Unrecognized command syntax: the command parameter is missing."
					else:			
						if fpar == defs.ACCESS:
							resp = "1{0}".format( self.acc )
						elif fpar == defs.STAT:
							resp = "1" + self.prepareStat()
						elif fpar == defs.DATAFILE:
							resp = "1" + self.datafile
						else:
							resp = "0Unrecognized command syntax."
							
				elif cmd == SHOW_LOG:
					n = 20
					if spar:
						try:
							n = int( spar )
						except ValueError as e:
							raise ISException(unrecognizedParameter, spar, 
								moreInfo="Number of lines only must contain digits.")
					resp = "1" + util.getLog(n)
														
				elif cmd == LIST:
					treeView = False
					for op in cmdOptions:
						if op[0] == TREE:
							treeView = True
					lres = []
					if not cmdData:
						self.fs.listItems( lres, treeView, 0, False)
					elif fpar.startswith(stor.SESPATH):
						self.tokens.listItems(lres, treeView, 0, False)
					elif fpar.startswith(stor.PERSPATH):
						self.perstokens.listItems( lres, treeView, 0, False)
					else:
						raise ISException(valueNotExists, fpar, "Section doesn't exist.")
					resp = "1"+"\n".join(lres)
					
				elif cmd in (ADD_TOKEN, LOAD_FILE, COPY_FILE):
					dest = None
					noOverwrite = True
					pers = False
					if not fpar:
						raise ISException(unrecognizedSyntax, moreInfo="No items specified.")
					for op in cmdOptions:
						if op[0] == DEST:
							if not op[1] or not self.fs.isPathValid(op[1]):
								raise ISException(unrecognizedParameter, 
									moreInfo="Parameter '{0}' must contain a valid section name.".format(DEST))
							dest = op[1]
								
						if op[0] == PERS:
							if dest:
								raise ISException(unrecognizedSyntax, 
									moreInfo="{0} and {1} cannot be both specified for one command.".format(
																					DEST, PERS))
							dest = stor.PERSPATH
							pers = True
						
						if op[0] == FORCE:
							noOverwrite = False
						
					# Without --dest or --pers options tokens are always added to /ses
					if not dest:
						dest = stor.SESPATH
						
					if cmd == ADD_TOKEN:
						log.debug("dest: {0} .".format( dest ) )
							
						for tok in cmdData:
							if dest:
								self.fs.addTokenToDest(dest, tok, noOverwrite )
							else:
								self.fs.addToken( tok, noOverwrite )
						
						if dest and dest.startswith(stor.PERSPATH):
							write_locked( self.data_fd, self.perstokens )
							
						resp = "1"
						
					elif cmd == LOAD_FILE:
						'''Load tokens from a file.'''
						frompars = util.getSwitches( cmdOptions, FROM_PARS )[0]
						log.debug("from_pars: {0}; dest: {1} .".format( frompars, dest ) )
							
						if not frompars:
							for filename in cmdData:
								if os.path.exists( filename ):
									stor.read_tokens_from_file(filename, tok, dest, noOverwrite)
								else:
									resp = "{0}File not found: {1}".format( valueNotExists, cmdData )
						else:
							stok = self.fs.getSectionFromStr(dest)
							for file in cmdData:
								stor.read_tokens_from_lines( file.split('\n'), stok, noOverwrite)
							
						resp = "1"
						
					elif cmd == COPY_FILE:
						frompars = util.getSwitches( cmdOptions, FROM_PARS )[0]
						src = cmdData[0]
						dst = cmdData[1]
						ret = None
						if dst[0] == ':': # cp from file to token
							if frompars:
								val = src
							else:
								with open(src) as f:
									val = f.read()
							tok = dst[1:] + " =" + val 
							self.fs.addTokenToDest(dest, tok, noOverwrite )
							ret = ""
						elif src[0] == ':': # cp from token to file
							src = src[1:]
							if not self.fs.isPathValid( src ):
								src = "{0}/{1}".format(stor.PERSPATH if pers else stor.SESPATH, fpar)
							
							ret = self.fs.getToken(src)
							
						resp = "1" + ret
				
				elif cmd in ( GET_TOKEN, REMOVE_TOKEN, REMOVE_SECTION):
					pers = util.getSwitches( cmdOptions, PERS)[0]
					if not self.fs.isPathValid( fpar ):
						fpar = "{0}/{1}".format(stor.PERSPATH if pers else stor.SESPATH, fpar)
					elif stor.isPathPers(fpar):
						pers = True
						
					log.debug( "pers: {0} ; fpar: {1}".format( pers, fpar ))
												
					if cmd == GET_TOKEN:
						resp = "1" + self.fs.getToken(fpar)
		
					elif cmd == REMOVE_TOKEN:
						self.fs.removeToken(fpar)
						if pers:
							stor.write_locked(self.data_fd, self.perstokens)
						resp = "1"
		
					elif cmd == REMOVE_SECTION:
						self.fs.removeSection(fpar)
						if pers:
							stor.write_locked(self.data_fd, self.perstokens)
						resp = "1"
						
				elif cmd == LOAD_FILE_SEC:
					if not fpar:
						file = self.encFile
					else:
						file = fpar
	
					read_sec_file( file, self.secTokCmd, self.sectokens  )
					resp = "1"
						
				elif cmd == GET_TOKEN_SEC:
					''' Get secure token. '''
					if not fpar:
						resp = "0No token specified."
					else:
						if not len( self.sectokens ):
							'''Sec tokens are not read yet. Read the default priv. file.'''
							if not self.defencread:
								read_sec_file( self.encFile, self.secTokCmd, self.sectokens )
								self.defencread = True
						resp = "1" + get_token( self.sectokens, fpar )
	
				elif cmd == REMOVE_TOKEN_SEC:
					self.sectokens.removeToken( fpar )
					resp = "1"
						
				elif cmd == REMOVE_SECTION_SEC:
					try:
						remove_section( self.sectokens, fpar )
						resp = "1"
					except ISException as e:
						resp = str( e )
						
				elif cmd == CLEAR_SEC:
					self.sectokens = getstor()
					resp = "1"
	
				elif cmd == CLEAR_SESSION:
					self.sectokens = getstor()
					self.tokens = getstor()
					resp = "1"
					
			except ISException as e:
				resp = str(e)
			except Exception as e:
				resp = "0" + e.args[0]
			except BaseException as e:
				resp = "0" + str( e )
				
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
		m = stor.Stor.statReg( self.tokens )
		ret += ( "\nSession tokens:\n------------------------\n")
		ret += util.printMap( m, 0 )
		m = stor.Stor.statReg( self.perstokens )
		ret += ( "\nPersistent tokens:\n------------------------\n")
		ret += util.printMap( m, 0 )
		ret += ( "\nCommands:\n------------------------\n")
		ret += util.printMap( self.mcmd, 0 )
		return ret		

def Server( servername, sockfile=None, host=None, port=None, acc=defs.PL_PRIVATE, datafile=None ):
	RegdServer( servername, sockfile, host, port, acc, datafile ).start_loop()
	
	
