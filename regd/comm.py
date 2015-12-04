'''
/********************************************************************
*	Module:			regd.comm
*
*	Created:		Jul 25, 2015
*
*	Abstract:		Communication with regd.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*********************************************************************/
'''
__lastedited__="2015-12-04 04:28:14"

import os, subprocess as sp, time
import regd.defs as defs, regd.util as util, regd.cli as cli
from regd.util import log, clp

rc = "regd"

def regdcmd( cpars, addr=None, servername = None, host = None, port = None ):
	'''Adapter for the Client() for using from other packages.'''
	sockfile = None
	if addr:
		if addr.find(":") != -1:
			host, _, port = addr.partition(":")
		else:
			servername = addr
			
	if not host:
		try:
			atuser, servername = util.parse_server_name( servername )
		except util.ISException as e:
			print( e )
			return e.code
		
		if not servername:
			servername = "regd"
	
		_, sockfile = util.get_filesock_addr( atuser, servername )
	
	res, ret = cli.doServerCmd( cpars, sockfile, host, port)
	util.logcomm.debug( "regdcmd: res: {0} ; ret: {1}".format( res, ret ) )
		
	return res, ret

class RegdComm:
	def __init__(self, servAddr=None, servername=None, host=None, port=None, datafile=None, acc=None):
		self.servAddr = servAddr
		self.servName = servername
		self.host = host
		self.port = port
		self.datafile = datafile
		self.acc = acc
	
	def startServer( self ):
		res, _ = self.checkServer()
		if res:
			return False, "Server with such name is already running."
		
		log.info( "Creating registry %s" % self.servName )
		try:
			args = [rc, defs.START_SERVER]
			if self.servName:
				args.append( clp(defs.SERVER_NAME ))
				args.append( self.servName )
			if self.host:
				args.append( "--host" )
				args.append( self.host )
			if self.port:
				args.append( "--port" )
				args.append( self.port )
			if self.acc:
				args.append( "--access" )
				args.append( self.acc )
			if self.datafile:
				args.append( "--datafile" )
				args.append( self.datafile )

			sp.Popen( args )
			time.sleep( 2 )
			res = True
			ret = "Server started successfully."
		except sp.CalledProcessError as e:
			res = False
			ret = "{0} {1} {2} {3}".format( rc, defs.START_SERVER, "returned non-zero:", e.output )
		
		if res:
			res, _ = self.checkServer()
			if not res:
				return False, "Server failed to start."
		
		return res, ret
	
	def sendCmd(self, m, args=None, kwargs=None ):
		addArgsToMap( m, args, kwargs )
		return regdcmd( m, addr=self.servAddr, servername=self.servName, 
						host=self.host, port=self.port )
	
	def checkServer(self):
		try:
			res, ret = regdcmd( { "cmd": defs.CHECK_SERVER }, addr=self.servAddr, servername=self.servName, 
							host=self.host,	port=self.port)
		except util.ISException as e:
			res = False 
			ret = str( e )
		return res, ret
	
	def restartServer(self):
		try:
			res, ret = regdcmd( { "cmd": defs.RESTART_SERVER }, addr=self.servAddr, servername=self.servName, 
							host=self.host,	port=self.port)
		except util.ISException as e:
			res = False 
			ret = str( e )
		return res, ret
	
	def stopServer(self):
		try:
			res, ret = regdcmd( { "cmd": defs.STOP_SERVER }, addr=self.servAddr, servername=self.servName, 
							host=self.host,	port=self.port)
			time.sleep(2)
		except util.ISException as e:
			res = False 
			ret = str( e )
		return res, ret
				
	def listRunningServers(self, lres):
		'''Searches the socket directory and returns a list with tuples:
		( server address, socket filename ).'''
		sockdir, _ = util.get_filesock_addr()
		if not os.path.exists(sockdir):
			return
		
		for fname in os.listdir(sockdir):
			servtype, first, sec = util.parse_sockfile_name(fname)
			fpath = os.path.join(sockdir, fname)
			if servtype == 1:
				lres.append( ( first, fpath ) )
			elif servtype == 2:
				lres.append( ( first + " : " + sec, fpath ) )
	
	def listTokens(self, lres, path, *args, **kwargs ):
		m = { "cmd": defs.LIST }
		if path:
			m["params"] = [path]
		res, ret = self.sendCmd(m, args, kwargs)

		lres.extend( ret )
		return res
	
	def loadFile( self, fname, *args, **kwargs ):
		m = { "cmd": defs.LOAD_FILE, "params": [fname] }
		return self.sendCmd(m, args, kwargs)	
		
	def addToken(self, nam, val, *args, **kwargs):
		if val:
			token = "{0} = {1}".format( nam, val )
		else:
			token = nam
		m = { "cmd": defs.ADD_TOKEN, "params": [token] }
		return self.sendCmd(m, args, kwargs)
	
	def getToken(self, nam, *args, **kwargs ):
		m = { "cmd": defs.GET_TOKEN, "params": [nam] }
		if "default" not in kwargs:
			return self.sendCmd(m, args, kwargs)
		else:
			defRet = kwargs["default"]
			del kwargs["default"]
			res, ret = self.sendCmd(m, args, kwargs)
			if not res:
				ret = defRet
			return res, ret

	def getTokenSec( self, nam, *args, **kwargs ):
		m = { "cmd": defs.GET_TOKEN_SEC, "params": [nam] }
		return self.sendCmd(m, args, kwargs)
	
	def createSection( self, path ):
		return regdcmd( { "cmd": defs.CREATE_SECTION, "params": path }, addr=self.servAddr, 
						servername=self.servName, host=self.host, port=self.port)
		
	def rename( self, src, dst, *args, **kwargs ):
		m = { "cmd": defs.RENAME, "params": [src, dst] }
		return self.sendCmd(m, args, kwargs)
	
	def logMessage(self, logName, message):
		s="{0}".format(time.strftime("%m-%d %H:%M:%S"))
		res, ret = self.addToken("/sav/log/"+logName + s, message, defs.SUM)
		
		
def addArgsToMap( m, args, kwargs ):
	if args:
		m.update( dict( zip( args, [True] * len( args ) ) ) )
	if kwargs:
		m.update( kwargs )
	