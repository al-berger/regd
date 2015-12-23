"""******************************************************************
*	Module:			regd
*
*	File name:		fs.py
*
*	Created:		2015-12-17 15:14:24
*
*	Abstract:		"File system"
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*
*******************************************************************"""

__lastedited__ = "2015-12-23 21:00:46"

import os, subprocess, shutil, io
from multiprocessing import Process, Pipe
from regd.stor import getstor
import regd.stor as stor
import regd.app as app
from regd.util import log, composeResponse, joinPath
from regd.app import IKException, ErrorCode, ROAttr
from regd.cmds import CmdProcessor, registerGroupHandler
import regd.util as util
import regd.defs as df
import regd.tok as modtok

# Class commands

FS_INFO = "FS_INFO"


class FS( CmdProcessor ):
	'''Regd server storage'''
	
	# Read-only fields
	datafile 	= ROAttr( "datafile", str() )
	binsecfile 	= ROAttr( "binsecfile", str() )
	
	# Command handlers
	cmdDefs = (
	( df.IF_PATH_EXISTS, "1", None, None, "chPathExists" ),
	( df.GETATTR, "1", {df.ATTRS}, None, "chGetAttr" ),
	( df.SETATTR, "1", {df.ATTRS}, None, "chSetAttr" ),
	( df.LIST, "?", None, { df.TREE, df.NOVALUES, df.RECURS }, "chListItems" ),
	( df.GET_ITEM, "1+", None, {df.PERS}, "chGetItem" ),
	( df.ADD_TOKEN, "1+", None, { df.FORCE, df.PERS, df.DEST, df.ATTRS, df.BINARY, df.SUM }, "chAddToken" ),
	( df.ADD_TOKEN_SEC, "1+", None, { df.FORCE, df.PERS, df.DEST, df.ATTRS, df.BINARY, df.SUM }, "chAddTokenSec" ),
	( df.LOAD_FILE, "1+", None, { df.FORCE, df.PERS, df.DEST, df.ATTRS, df.FROM_PARS }, "chLoadFile" ),
	( df.COPY_FILE, "2", None, { df.FORCE, df.PERS, df.DEST, df.ATTRS, df.BINARY }, "chCopyFile" ),
	( df.REMOVE_TOKEN, "1+", None, {df.PERS}, "chRemoveToken" ),
	( df.REMOVE_SECTION, "1+", None, {df.PERS}, "chRemoveSection" ),
	( df.CREATE_SECTION, "1+", None, {df.PERS}, "chCreateSection" ),
	( df.RENAME, "1+", None, {df.PERS}, "chRename" ),
	( df.LOAD_FILE_SEC, "?", None, None, "chLoadFileSec" ),
	( df.GET_TOKEN_SEC, "1", None, None, "chGetTokenSec" ),
	( df.REMOVE_TOKEN_SEC, "1", None, None, "chRemoveTokenSec" ),
	( df.REMOVE_SECTION_SEC, "1", None, None, "chRemoveSectionSec" ),
	( df.CLEAR_SEC, "0", None, None, "chClearSec" ),
	( df.CLEAR_SESSION, "0", None, None, "chClearSessionTokens" ), 
	( FS_INFO, "?", None, None, "chFsInfo" ) 
	)

	def __init__(self, conn, datafile, binsecfile=None ):
		super( FS, self ).__init__( conn )
		
		self.datafile = datafile
		self.binsecfile = binsecfile
		self.info = {}
		self.cont = True
		
		self.fs 		= getstor( rootStor=None, mode=0o555 )
		
		self.tokens 	= getstor( rootStor=None, mode=0o777 )
		self.bintokens 	= getstor( rootStor = None, mode=0o777)
		
		self.fs[''] = getstor(rootStor=None, mode=0o555)
		self.fs[''][stor.SESNAME] = self.tokens
		# Persistent tokens
		# Bin section tokens
		self.fs[''][stor.BINNAME] = self.bintokens
		if self.binsecfile:
			self.fs.setItemAttr( stor.BINPATH, ( "{0}={1}".format( 
					stor.SItem.persPathAttrName, self.binsecfile ), ) )
			
		self.tokens.rootStor 		= self.tokens
		self.bintokens.rootStor 	= self.bintokens
		
		self.sectokens = getstor(rootStor=None)
			
		self.useruid = None

		# Default encrypted file name
		self.encFile = app.homedir + "/.sec/safestor.gpg"
		# Flag showing whether the default enc. file has been read
		self.defencread = False
		# Command line command for reading encrypted file
		self.secTokCmd = df.READ_ENCFILE_CMD
		
		if self.datafile:
			self.perstokens = getstor( rootStor=None, mode=0o777 )
			self.fs[''][stor.PERSNAME] = self.perstokens
			self.fs.setItemAttr( stor.PERSPATH, ( "{0}={1}".format( 
						stor.SItem.persPathAttrName, self.datafile ), ) )
			self.perstokens.rootStor 	= self.perstokens
			
			try:
				fhd = {'cur':None}
				stor.treeLoad = True
				self.fs[''][stor.PERSNAME].serialize( fhd, read = True )
				stor.treeLoad = False
				for v in fhd.values():
					if v: v.close()
				# read_locked( self.data_fd, self.perstokens, defs.overwrite )
				# self.data_fd.close()
			except IKException as e:
				log.error( "Cannot read the data file: %s" % ( str( e ) ) )
				raise IKException( ErrorCode.operationFailed )
		else:
			print( "Server's data file is not specified. Persistent tokens are not enabled.")

		if self.binsecfile:
			try:
				fhd = {'cur':None}
				stor.treeLoad = True
				self.fs[''][stor.BINNAME].serialize( fhd, read = True )
				stor.treeLoad = False
				for v in fhd.values():
					if v: v.close()
			except IKException as e:
				log.error( "Cannot read the bin_section file: %s" % ( str( e ) ) )
				raise IKException( ErrorCode.operationFailed )			

		d = {}
		app.read_conf( d )

		if "encfile" in d:
			self.encFile = d["encfile"]
		if "encfile_read_cmd" in d:
			self.secTokCmd = d["encfile_read_cmd"]
		
	def __getattr__( self, attrname ):
		pass
		#return getattr( self.fs, attrname )
		
	def getTokenSec( self, pathName ):
		'''Get secure token'''
		if not len( self.sectokens ):
			'''Sec tokens are not read yet. Read the default priv. file.'''
			if not self.defencread:
				self.read_sec_file()
				self.defencread = True
		return self.sectokens.getItem( pathName )

	def removeTokenSec( self, pathName ):
		'''Remove secure token'''
		self.sectokens.removeItem( pathName )

	def removeSectionSec( self, pathName ):
		'''Remove secure section'''
		self.sectokens.removeItem( pathName )

	def clearTokensSec( self ):
		'''Remove secure token'''
		self.sectokens.clear()

	def clearSessionTokens( self ):
		'''Remove secure token'''
		self.fs[''][stor.SESNAME].clear()

	def read_sec_file( self, filename=None, cmd=None, addMode = df.noOverwrite ):
		'''Read secure tokens from a file with a user command'''
		if not filename:
			filename = self.encFile

		if not os.path.exists( filename ):
			log.error( "Cannot find encrypted data file. Exiting." )
			raise IKException( ErrorCode.operationFailed, "File not found." )

		try:
			if not cmd:
				cmd = self.secTokCmd.replace( "FILENAME", "{0}" ).format( filename )
			ftxt = subprocess.check_output( cmd,
								shell = True, stderr = subprocess.DEVNULL )
		except subprocess.CalledProcessError as e:
			log.error( ftxt )
			raise IKException( ErrorCode.operationFailed, e.output )
		
		fh = io.BytesIO( ftxt )
		self.sectokens.readFromFile( fh=fh, addMode=addMode )

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
	
	@staticmethod
	def start_loop( conn, datafile, binsectfile ):
		'''Create FS instance and start loop'''
		fs = FS( conn, datafile, binsectfile )
		log.info( "Starting listening for messages..." )
		fs.listenForMessages( fs.serialize )
		log.info( "Ended listening for messages. Quitting..." )
		return 0
		
	def loop( self ):
		self.cont = True
		while self.cont:
			if self.datafile:
				if self.lock_seriz.acquire( blocking = False ):
					self.serialize()
					self.lock_seriz.release()
			self.quitCond.acquire()
			self.quitCond.wait( 30 )

	def chFsInfo( self, cmd ):
		path = cmd.get("params")
		if not path:
			return util.printMap( self.info, 0 )
		else:
			path = path[0]
			item = self.getItem( path )
			m = item.stat()
			return util.printMap( m, 0 )

	def chPathExists( self, cmd ):
		'''Return True if a token path exists'''
		par = cmd["params"][0]
		try:
			self.fs.getItem( par )
			return composeResponse()
		except IKException as e:
			if e.code == ErrorCode.objectNotExists:
				return composeResponse( "0" )
			else:
				raise

	def chGetAttr( self, cmd ):
		'''Return item's attribute'''

		"""Query for attributes of a storage item.
		Syntax: GETATTR <itempath> [attrname]
		Without 'attrname' returns 'st_stat' attributes like function 'getattr'.
		With 'attrname' works like 'getxattr'.
		"""
		attrNames = None
		par = cmd["params"][0]
		if df.ATTRS in cmd:
			attrNames = cmd[df.ATTRS]
		m = self.fs.getItemAttr( par, attrNames )
		return composeResponse( '1', m )

	def chSetAttr( self, cmd ):
		'''Set an item's attribute'''
		
		"""Set attributes of a storage item.
		Syntax: SETATTR <itempath> <attrname=attrval ...>"""

		par = cmd["params"][0]
		item = self.fs.setItemAttr( par, cmd[df.ATTRS] )
		item.markChanged()

		# When the backing storage path attribute is set, the storage file
		# is overwritten with the current content of the item. In order to
		# read the file contents into an item, loadFile function is used.
		if [x for x in cmd[df.ATTRS] if x.startswith( stor.SItem.persPathAttrName + "=" )]:
			# TODO: move the call to fs.serialize to item, where thread sync is 
			with self.lock_seriz:
				self.fs.serialize()

		return composeResponse()

	def chListItems( self, cmd ):
		'''List items'''
		par = cmd["params"]
		swNovals = df.NOVALUES in cmd
		swTree = df.TREE in cmd
		swRecur = df.RECURS in cmd
		lres = []
		if not par:
			self.fs[''].listItems( lres = lres, bTree = swTree, nIndent = 0, bNovals = swNovals,
							relPath = None, bRecur = swRecur )
		else:
			sect = self.fs.getItem( par[0] )
			sect.listItems( lres = lres, bTree = swTree, nIndent = 0, bNovals = swNovals,
						relPath = None, bRecur = swRecur )

		return composeResponse( '1', lres )

	def _getAddOptions( self, cmd ):
		par = cmd["params"]
		if not par:
			raise IKException( ErrorCode.unrecognizedSyntax, moreInfo = "No items specified." )
		dest = None
		addMode = df.noOverwrite
		if df.DEST in cmd:
			if not cmd[df.DEST] or not self.fs.isPathValid( cmd[df.DEST][0] ):
				raise IKException( ErrorCode.unrecognizedParameter,
						moreInfo = "Parameter '{0}' must contain a valid section name.".format( df.DEST ) )
			dest = cmd[df.DEST][0]
		if df.PERS in cmd:
			if dest:
				raise IKException( ErrorCode.unrecognizedSyntax,
						moreInfo = "{0} and {1} cannot be both specified for one command.".format( 
																		df.DEST, df.PERS ) )
			dest = stor.PERSPATH
		if df.FORCE in cmd:
			addMode = df.overwrite
		if df.SUM in cmd:
			addMode = df.sumUp
		if df.ATTRS in cmd:
			attrs = util.pairsListToMap( cmd[df.ATTRS] )
		else:
			attrs = None

		return dest, addMode, attrs

	def chAddToken( self, cmd ):
		'''Add item'''
		dest, addMode, attrs = self._getAddOptions( cmd )
		cnt = 0
		with self.lock_seriz:
			for tok in cmd["params"]:
				if (dest and dest.startswith( stor.BINPATH ) ) or \
						tok.startswith( stor.BINPATH ):
					self.handleBinToken( dest, tok, cmd )
					continue
	
				# Without --dest or --pers options tokens with relative path
				# are always added to session tokens
				if not dest and tok[0] != '/':
					dest = stor.SESPATH
	
				binaryVal = None
				if df.BINARY in cmd:
					if not cmd[df.BINARY] or len( cmd[df.BINARY] ) < cnt + 1:
						raise IKException( ErrorCode.unknownDataFormat, tok )
					binaryVal = cmd[df.BINARY][cnt]
					attrs[stor.SItem.persPathAttrName] = df.BINARY
					cnt += 1
	
				if dest:
					tok=joinPath(dest, tok)
				sec = self.fs.addItem( tok=tok, addMode=addMode, 
										binaryVal=binaryVal, attrs = attrs )
	
				if sec: sec.markChanged()

		return composeResponse( )

	def chAddTokenSec( self, cmd ):
		'''Add item'''
		dest, addMode, attrs = self._getAddOptions( cmd )
		cnt = 0

		for tok in cmd["params"]:
			binaryVal = None
			if df.BINARY in cmd:
				if not cmd[df.BINARY] or len( cmd[df.BINARY] ) < cnt + 1:
					raise IKException( ErrorCode.unknownDataFormat, tok )
				binaryVal = cmd[df.BINARY][cnt]
				attrs[stor.SItem.persPathAttrName] = df.BINARY
				cnt += 1

			if dest:
				tok=joinPath(dest, tok)
			sec = self.fs.sectokens.addItem( tok=tok, addMode=addMode, 
									binaryVal=binaryVal, attrs = attrs )

			# TODO: serialization of secure items
			if sec: sec.markChanged()

		return composeResponse()

	def chLoadFile( self, cmd ):
		'''Load tokens from a file.'''
		dest, addMode, attrs = self._getAddOptions( cmd )
		if not dest:
			dest = stor.SESPATH
		swFromPars = df.FROM_PARS in cmd
			
		if not swFromPars:
			for filename in cmd["params"]:
				if os.path.exists( filename ):
					self.fs.readFromFile( filePath=filename, dest=dest, addMode=addMode )
				else:
					raise IKException( ErrorCode.objectNotExists, filename, "File not found" )
		else:
			for file in cmd["params"]:
				fh = io.BytesIO( file.encode() )
				self.fs.readFromFile( fh=fh, dest=dest, addMode=addMode )

		return composeResponse()

	def chCopyFile( self, cmd ):
		'''Copy file contents to an item'''
		dest, addMode, attrs = self._getAddOptions( cmd )
		swFromPars = df.FROM_PARS in cmd
		src = cmd["params"][0]
		dst = cmd["params"][1]
		ret = None
		if dst[0] == ':':  # cp from file to token
			if swFromPars:
				val = src
			else:
				with open( src ) as f:
					val = f.read()
			tok = dst[1:] + " =" + val
			self.fs.addItem( tok=util.joinPath(dest, tok), addMode=addMode, attrs=attrs )
			ret = ""
		elif src[0] == ':':  # cp from token to file
			src = src[1:]
			if not self.fs.isPathValid( src ):
				src = "{0}/{1}".format( stor.PERSPATH if df.PERS in cmd else stor.SESPATH, 
									src )

			# File is written on the client side
			ret = self.fs.getItem( src ).val

		return composeResponse( '1', ret )

	def _getItemFeeder( self, cmd ):
		swPers = df.PERS in cmd
		for i in cmd["params"]:
			if i[0] != '/':
				ret = "{0}/{1}".format( stor.PERSPATH if swPers else stor.SESPATH, i )
			else:
				ret = i
			yield ret

	def chGetItem( self, cmd ):
		'''Get item'''
		feeder = self._getItemFeeder( cmd )
		lres = []
		for i in feeder:
			lres.append( self.fs.getItem( i ) )

		return composeResponse( '1', lres )

	def chRemoveToken( self, cmd ):
		'''Remove token'''
		feeder = self._getItemFeeder( cmd )
		for i in feeder:
			self.fs.removeItem( i ).markChanged()

		return composeResponse( )

	def chRemoveSection( self, cmd ):
		'''Remove section'''
		feeder = self._getItemFeeder( cmd )
		for i in feeder:
			self.fs.removeItem( i ).markChanged()

		return composeResponse( )

	def chCreateSection( self, cmd ):
		'''Create section'''
		feeder = self._getItemFeeder( cmd )
		for i in feeder:
			sec = self.fs.addItem( i )
			if df.ATTRS in cmd:
				sec.setAttrs( cmd[df.ATTRS] )
				sec.readFromFile( updateFromStorage = True )
			sec.markChanged()

		return composeResponse( )

	def chRename( self, cmd ):
		'''Rename item'''
		feeder = self._getItemFeeder( cmd )
		for i in feeder:
			self.fs.rename( i ).markChanged()

		return composeResponse( )

	def chLoadFileSec( self, cmd ):
		'''Rename item'''
		file = cmd.get("params")
		if not file:
			file = None
		else:
			file = file[0]
		
		self.fs.read_sec_file( file )
		return composeResponse( )

	def chGetTokenSec( self, cmd ):
		'''Get secure token'''
		par = cmd["params"][0]
		tok = self.fs.getTokenSec( par ).val
		return composeResponse( '1', tok )

	def chRemoveTokenSec( self, cmd ):
		'''Remove secure token'''
		self.fs.removeTokenSec( cmd["params"][0] )
		return composeResponse()

	def chRemoveSectionSec( self, cmd ):
		'''Remove secure section'''
		self.fs.removeSectionSec( cmd["params"][0] )
		return composeResponse()

	def chClearSec( self, cmd ):
		'''Clear secure tokens'''
		self.fs.clearTokensSec( )
		return composeResponse()

	def chClearSessionTokens( self, cmd ):
		'''Clear session tokens'''
		self.fs.clearTokensSec( )
		self.fs.clearSessionTokens( )
		return composeResponse()

def startStorage( datafile, binsectfile ):
	'''Starts storage in new process'''
	connHere, connThere = Pipe( True )
	
	def sendMsgToStorage( cmd ):
		'''Forwarder of messages to storage'''
		connHere.send( cmd )
		return connHere.recv()
		
	FS.registerGroupHandlers( sendMsgToStorage )
	
	log.info( "Starting storage process..." )
	p = Process( target=FS.start_loop, args=(connThere, datafile, binsectfile), 
			name="Regd Storage" )
	p.start()
	if p.is_alive():
		log.info( "Storage started OK." )
	else:
		log.info( "Failed to start storage." )
		raise IKException( ErrorCode.operationFailed, "Failed to start storage."  )
	
	return connHere
