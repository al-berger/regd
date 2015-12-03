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
__lastedited__ = "2015-12-02 20:43:27"

import sys, time, subprocess, os, pwd, signal, socket, struct, datetime, threading, tempfile
import ipaddress, shutil
import fcntl  # @UnresolvedImport
import regd.util as util, regd.defs as defs
from regd.util import log, ISException, permissionDenied, persistentNotEnabled, valueNotExists,\
	operationFailed, sigHandler, unrecognizedParameter,\
	unrecognizedSyntax, composeResponse, objectNotExists, unknownDataFormat
from regd.stor import EnumMode, read_locked, write_locked, get_token,\
	read_sec_file, remove_section, remove_token, getstor
import regd.stor as stor
import __main__  # @UnresolvedImport
from regd.defs import *  # @UnusedWildImport

lock_seriz = threading.Lock()

class RegdServer:
	def __init__(self, servername, sockfile, host, port, acc, datafile ):
		self.servername = servername
		self.sockfile = sockfile
		self.host = host
		self.port = port
		self.acc = acc
		self.datafile = datafile
		self.data_fd = None
		self.sock = None
		self.disposed = False
		
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
		if datafile:
			self.fs.setSItemAttr("/sav", ("{0}={1}".format(
					stor.SItem.Attrs.persPath.name, datafile),))  # @UndefinedVariable
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
			'''
			# Obtaining the lock
			try:
				self.data_fd = open( self.datafile, "r+b", buffering=1 )
				#log.debug("Data file fileno: %i" % (self.data_fd.fileno()))
				#fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB )
			except OSError as e:
				print("Error: data file \"{0}\" could not be opened: {1}".format(datafile, e.strerror), 
				"Server is not started.")
				raise ISException(operationFailed)
		else:
			print( "Server's data file is not specified. Persistent tokens are not enabled.")
			
		if self.data_fd:
		'''
			try:
				fhd={'cur':None}
				stor.treeLoad = True
				self.fs['']['sav'].serialize( fhd, read=True)
				stor.treeLoad = False
				for v in fhd.values():
					if v: v.close()
				#read_locked( self.data_fd, self.perstokens, defs.overwrite )
				#self.data_fd.close()
			except ISException as e:
				log.error( "Cannot read the data file: %s" % ( str(e)))
				raise ISException(operationFailed)
			
		def signal_handler( signal, frame ):
			self.sock.close()
			self.close()
			sys.exit( 1 )
			
		sigHandler.push(signal.SIGINT, signal_handler)
		sigHandler.push(signal.SIGTERM, signal_handler)
		sigHandler.push(signal.SIGHUP, signal_handler)
		sigHandler.push(signal.SIGABRT, signal_handler)
		sigHandler.push(signal.SIGALRM, signal_handler)
		
	def __del__(self):
		# close() is better to be called earlier in order for closing routines not be
		# called when some modules are unloaded 
		self.close()
		
	def close(self):
		if self.disposed:
			return
		self.disposed = True
		self.serialize()
		if os.path.exists( self.sockfile ):
			log.info("Signal is received. Unlinking socket file...")
			os.unlink( self.sockfile )
		if self.data_fd:
			fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_UN )
		
	def start_loop(self):
		
		if not self.host and os.path.exists( self.sockfile ):
			log.info("Socket file for a server with name already exists. Checking for the server process.")
			'''Socket file may remain after an unclean exit. Check if another server is running.'''
			try:
				# If the server is restarted, give the previous instance time to exit cleanly.
				time.sleep( 2 )
				if self.servername and self.servername != "regd":
					s = "ps -ef | grep '{0}(/cli.py)? start .*{1} {2}' | grep -v grep".format( 
												APPNAME, 
												util.clp(defs.SERVER_NAME), 
												self.servername )
				else:
					s = "ps -ef | grep -E '{0}(/cli.py)? start' | grep -v '{1}' | grep -v grep".format( 
												APPNAME, 
												util.clc(defs.SERVER_NAME) )
					
				
				res = subprocess.check_output( s, shell = True ).decode( 'utf-8' )
				
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
			log.info( "Server process is not found. Unlinking the existing socket file.")
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
				self.sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
				self.sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
				self.sock.bind( ( self.host, int(self.port) ) )
				with open( self.sockfile, "w" ) as f:
					f.write('')
				
			else:
				self.sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
				self.sock.bind( self.sockfile )
				os.chmod( self.sockfile, mode=0o777 )
				
		except OSError as e:
			log.error( "Cannot create or bind socket: %s" % (e) )
			return -1
		
		self.sock.settimeout( 30 )
		self.sock.listen( 1 )
		self.loop( self.sock )
	
	def loop(self, sock):
		self.cont = True
		self.exitcode = 0
		connection = None
		
		while True:
			try:
				connection, client_address = sock.accept()
			except socket.timeout:
				if not os.path.exists( self.sockfile ):
					log.error("Socket file {0} is gone. Exiting.".format( self.sockfile ) )
					self.cont = False
					self.exitcode = 1
				else:
					if self.datafile:
						#TODO: in thread
						if lock_seriz.acquire( blocking=False ):
							self.serialize( )
							lock_seriz.release()
					continue
			
			except Exception as e:
				print( "Exception occured: ", e)
				self.cont = False
				
			if not self.cont:
				log.info("Server exiting.")
				if connection:
					connection.shutdown( socket.SHUT_RDWR )
					connection.close()
				if self.data_fd:
					log.info("Unlocking data file.")
					fcntl.lockf( self.data_fd.fileno(), fcntl.LOCK_UN )
				sys.exit( self.exitcode )
											
			threading.Thread( target=self.handle_connection, name="handle_connection", 
								args=(connection, client_address) ).start()

	def handle_connection(self, *args):
		connection = args[0] 
		client_address = args[1]
		try:
			self._handle_connection(connection, client_address)
		except ISException as e:
			log.error( ( "Exception while handling connection. Continuing loop." 
						"Client: %s ; Exception: %s") % (client_address, e))

		except Exception as e:
			log.error("Exception in server loop. Exiting. %s" % (e))
			self.cont = False
			self.exitcode = -1

		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()

	def _handle_connection(self, connection, client_address):
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
		bresp = bytearray()
		cmd = None
		try:
			cmd = util.parsePacket(data, cmdOptions, cmdData)
			log.debug( "command received: {0} {1}".format( cmd, cmdData ) )
			log.debug( "command options: {0}".format( cmdOptions ) )
		except Exception as e:
			composeResponse(bresp, "0", str(e))
			

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
			composeResponse(bresp, "0", str( ISException( permissionDenied, cmd ) ) )
		elif not self.data_fd and util.getSwitches(cmdOptions, PERS)[0]:
			composeResponse(bresp, "0", str( ISException(persistentNotEnabled) ) )
		elif not len(bresp):
			self.mcmd[cmd] = 1 if cmd not in self.mcmd else self.mcmd[cmd]+1
			
			# -------------- Command handling -----------------
			fpar = None
			if len( cmdData ):
				fpar = cmdData[0]
			spar = None
			if len( cmdData ) > 1:
				spar = cmdData[1] 
				
			swPers, swTree, swForce, swFromPars, swRecur = util.getSwitches( cmdOptions, 
												PERS, TREE, FORCE, FROM_PARS, RECURS )
			optDest, optBinary = util.getOptions( cmdOptions, DEST, BINARY)
			
			optmap = util.getOptionMap( cmdOptions )
			
			log.debug("fpar: {0} ; spar: {1}".format( fpar, spar ) )
			
			retCode = '0'
				
			try:
			
				if cmd == STOP_SERVER:
					composeResponse( bresp )
	
				elif cmd == CHECK_SERVER:
					resp = "Up and running since {0}\nUptime:{1}.".format(	
							str(self.timestarted).rpartition(".")[0], 
							str(datetime.datetime.now() - self.timestarted).rpartition(".")[0])
					composeResponse(bresp, '1', resp )
					
				elif cmd == VERS:
					composeResponse( bresp, '1', "Regd version on server: " + defs.__version__ )
				
				elif cmd == REPORT:
					if not fpar:
						resp = "Unrecognized command syntax: the command parameter is missing."
					else:
						retCode = '1'
						if fpar == defs.ACCESS:
							resp = "{0}".format( self.acc )
						elif fpar == defs.STAT:
							resp = self.prepareStat()
						elif fpar == defs.DATAFILE:
							resp = self.datafile
						else:
							retCode = '0'
							resp = "Unrecognized command syntax."
							
					composeResponse(bresp, retCode, resp ) 
					
				elif cmd == INFO:
					resp = "{0} : {1}\n".format( defs.APPNAME, defs.__description__)
					resp += "License: {0}\n".format(defs.__license__ )
					resp += "Homepage: {0}\n\n".format(defs.__homepage__ )
					resp += "Server version: {0}\n".format( defs.rversion)
					resp += "Server datafile: {0}\n".format( self.datafile)
					resp += "Server access: {0}\n".format( self.acc )
					resp += "Server socket file: {0}\n".format( self.sockfile )
					
					composeResponse(bresp, "1", resp ) 
					
				elif cmd == IF_PATH_EXISTS:
					try:
						self.fs.getSItem( fpar )
						composeResponse( bresp )
					except ISException as e:
						if e.code == objectNotExists:
							composeResponse( bresp, "0" )
						else:
							raise 						
							
				elif cmd == GETATTR:
					'''Query for attributes of a storage item.
					Syntax: GETATTR <itempath> [attrname]
					Without 'attrname' returns 'st_stat' attributes like function 'getattr'.
					With 'attrname' works like 'getxattr'.
					'''
					attrNames = None
					if ATTRS in optmap:
						attrNames = optmap[ATTRS]
					m = self.fs.getSItemAttr( fpar, attrNames )
					composeResponse(bresp, '1', m)					
							
				elif cmd == SETATTR:
					'''Set attributes of a storage item.
					Syntax: SETATTR <itempath> <attrname=attrval ...>'''
					item = self.fs.setSItemAttr( fpar, optmap[ATTRS] )
					
					# When the backing storage path attribute is set, the storage file 
					# is overwritten with the current content of the item. In order to
					# read the file contents into an item, loadFile function is used.
					if [x for x in optmap[ATTRS] if x.startswith(stor.SItem.persPathAttrName + "=")]:
						#item.writeToFile()
						with lock_seriz:
							self.serialize()  
					
					composeResponse( bresp )
					
				elif cmd == SHOW_LOG:
					n = 20
					if spar:
						try:
							n = int( spar )
						except ValueError as e:
							raise ISException(unrecognizedParameter, spar, 
								moreInfo="Number of lines only must contain digits.")
					composeResponse( bresp, '1', util.getLog(n) )
					
				elif cmd == LIST:
					swNovals = NOVALUES in optmap
					lres = []
					if not cmdData:
						self.fs[""].listItems( lres=lres, bTree=swTree, nIndent=0, bNovals=swNovals,
										relPath=None, bRecur=swRecur)
					else:
						sect = self.fs.getSectionFromStr(fpar)
						sect.listItems(lres=lres, bTree=swTree, nIndent=0, bNovals=swNovals,
									relPath=None, bRecur=swRecur)
					
					#composeResponse( bresp, '1', "\n".join(lres) )
					composeResponse( bresp, '1', lres )
					
				elif cmd in (ADD_TOKEN, ADD_TOKEN_SEC, LOAD_FILE, COPY_FILE):
					dest = None
					addMode = defs.noOverwrite
					if not fpar:
						raise ISException(unrecognizedSyntax, moreInfo="No items specified.")
					if DEST in optmap:
						if not len(optmap[DEST]) or not self.fs.isPathValid(optmap[DEST][0]):
							raise ISException(unrecognizedParameter, 
									moreInfo="Parameter '{0}' must contain a valid section name.".format(DEST))
						dest = optmap[DEST][0]
					if PERS in optmap:
						if dest:
							raise ISException(unrecognizedSyntax, 
									moreInfo="{0} and {1} cannot be both specified for one command.".format(
																					DEST, PERS))
						dest = stor.PERSPATH
					if FORCE in optmap:
						addMode = defs.overwrite
					if SUM in optmap:
						addMode = defs.sumUp
					if ATTRS in optmap:
						attrs=util.pairsListToMap(optmap[ATTRS])
					else:
						attrs=None

					if cmd in (ADD_TOKEN, ADD_TOKEN_SEC):
						log.debug("dest: {0} .".format( dest ) )
						cnt = 0
						for tok in cmdData:
							# Without --dest or --pers options tokens are always added to /ses
							if not dest and tok[0] != '/' and cmd != ADD_TOKEN_SEC:
								dest = stor.SESPATH

							binaryVal = None
							if defs.BINARY in optmap:
								if not optmap[defs.BINARY] or len(optmap[defs.BINARY]) < cnt+1:
									raise ISException( unknownDataFormat, tok )
								binaryVal = optmap[defs.BINARY][cnt]
								attrs[stor.SItem.Attrs.encoding.name] = defs.BINARY  # @UndefinedVariable
								cnt += 1
							sec = None
							if cmd == ADD_TOKEN:
								if dest:
									sec = self.fs.addTokenToDest(dest, tok, addMode, binaryVal,attrs=attrs )
								else:
									sec = self.fs.addToken( tok, addMode, binaryVal,attrs=attrs )
							else:
								if dest:
									sec = self.sectokens.addTokenToDest(dest, tok, addMode, binaryVal,attrs=attrs )
								else:
									sec = self.sectokens.addToken( tok, addMode, binaryVal,attrs=attrs )
							
							if sec: sec.markChanged()
													
						composeResponse( bresp )
						
					elif cmd == LOAD_FILE:
						'''Load tokens from a file.'''
						log.debug("from_pars: {0}; dest: {1} .".format( swFromPars, dest ) )
							
						if not swFromPars:
							for filename in cmdData:
								if os.path.exists( filename ):
									stor.read_tokens_from_file(filename, self.fs, addMode)
								else:
									raise ISException( objectNotExists, filename, "File not found")
						else:
							if not dest:
								dest = stor.SESPATH
							stok = self.fs.getSectionFromStr(dest)
							for file in cmdData:
								stor.read_tokens_from_lines( file.split('\n'), stok, addMode)
							
						composeResponse( bresp )
						
					elif cmd == COPY_FILE:
						src = cmdData[0]
						dst = cmdData[1]
						ret = None
						if dst[0] == ':': # cp from file to token
							if swFromPars:
								val = src
							else:
								with open(src) as f:
									val = f.read()
							tok = dst[1:] + " =" + val 
							self.fs.addTokenToDest(dest, tok, addMode )
							ret = ""
						elif src[0] == ':': # cp from token to file
							src = src[1:]
							if not self.fs.isPathValid( src ):
								src = "{0}/{1}".format(stor.PERSPATH if swPers else stor.SESPATH, fpar)
							
							ret = self.fs.getTokenVal(src)
							
						composeResponse( bresp, '1', ret )
						
				
				elif cmd in ( GET_TOKEN, REMOVE_TOKEN, CREATE_SECTION, REMOVE_SECTION, RENAME ):
					if fpar[0] != '/' or not self.fs.isPathValid( fpar ):
						fpar = "{0}/{1}".format(stor.PERSPATH if swPers else stor.SESPATH, fpar)
					elif stor.isPathPers(fpar):
						swPers = True
						
					log.debug( "pers: {0} ; fpar: {1}".format( swPers, fpar ))
												
					if cmd == GET_TOKEN:
						composeResponse( bresp, '1', self.fs.getTokenVal(fpar) )
						log.debug( "response: {0} ".format(bresp) )
					else:
						if cmd == REMOVE_TOKEN:
							sec = self.fs.removeToken(fpar)
						elif cmd == CREATE_SECTION:
							sec = self.fs.createSection( fpar )
							if ATTRS in optmap:
								sec.setAttrs( optmap[ATTRS] )
								sec.readFromFile( updateFromStorage=True )
						elif cmd == REMOVE_SECTION:
							sec = self.fs.removeSection(fpar)
						elif cmd == RENAME:
							sec = self.fs.rename(fpar, spar)
						
						if sec:
							sec.markChanged()
						
						composeResponse( bresp )
						
				elif cmd == LOAD_FILE_SEC:
					if not fpar:
						file = self.encFile
					else:
						file = fpar
	
					read_sec_file( file, self.secTokCmd, self.sectokens  )
					composeResponse( bresp )
						
				elif cmd == GET_TOKEN_SEC:
					''' Get secure token. '''
					if not fpar:
						composeResponse( bresp, '0', "No token specified." )
					else:
						if not len( self.sectokens ):
							'''Sec tokens are not read yet. Read the default priv. file.'''
							if not self.defencread:
								read_sec_file( self.encFile, self.secTokCmd, self.sectokens )
								self.defencread = True
						#resp = "1" + get_token( self.sectokens, fpar )
						composeResponse( bresp, '1', self.sectokens.getTokenVal( fpar ) )
	
				elif cmd == REMOVE_TOKEN_SEC:
					self.sectokens.removeToken( fpar )
					composeResponse( bresp )
						
				elif cmd == REMOVE_SECTION_SEC:
					remove_section( self.sectokens, fpar )
					composeResponse( bresp )
						
				elif cmd == CLEAR_SEC:
					self.sectokens = getstor()
					composeResponse( bresp )
	
				elif cmd == CLEAR_SESSION:
					self.sectokens = getstor()
					self.tokens = getstor()
					composeResponse( bresp )
					
			except ISException as e:
				composeResponse(bresp, '0', str(e) )
			except Exception as e:
				composeResponse(bresp, '0', e.args[0] )
			except BaseException as e:
				composeResponse(bresp, '0', str(e) )
				
		try:
			if not len( bresp ):
				composeResponse(bresp, "0", "Command not recognized")
			util.sendPack(connection, bresp )
		except OSError as er:
			log.error( "Socket error {0}: {1}\nClient address: {2}\n".format( 
							er.errno, er.strerror, client_address ) )

		if cmd == STOP_SERVER and perm:
			log.info( "Stopping server." )
			if self.sockfile:
				os.unlink( self.sockfile )
			self.cont = False
			signal.alarm(1)
		
		return
			
	def prepareStat(self):
		'''Gather statistics'''
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
	
	def serialize(self):
		'''Serializing persistent tokens.'''
		if not len( stor.changed ):
			return
		with stor.lock_changed:
			ch_ = stor.changed[:]
			stor.changed = []
		commonPath = os.path.commonpath( [x.pathName() for x in ch_] )
		if commonPath == "/": commonPath = stor.PERSPATH
		sec = self.fs.getSectionFromStr( commonPath )
		fhd = {}
		sec.serialize( fhd, read = False )
		for fpath, fh in fhd.items():
			if fpath == "cur":
				continue
			fh.close()
			shutil.move(fpath, fpath[:-4])	
		

def Server( servername, sockfile=None, host=None, port=None, acc=defs.PL_PRIVATE, datafile=None ):
	srv = RegdServer( servername, sockfile, host, port, acc, datafile )
	srv.start_loop()
	srv.close()
	
	
