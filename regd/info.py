"""******************************************************************
*	Module:			regd
*	
*	File name:		info.py
*
*	Created:		2015-12-19 10:18:19
*
*	Abstract:		Info module.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*******************************************************************"""

__lastedited__ = "2016-04-02 10:00:16"

from datetime import datetime
from regd.cmds import CmdSwitcher, CmdProcessor
import regd.util as util
import regd.appsm.app as app
from regd.util import log, composeResponse
from regd.appsm.app import IKException, ErrorCode
import regd.defs as df

class Info( CmdProcessor ):
	'''Info'''
	cmdDefs = ( 
		( df.CHECK_SERVER, "0", None, None, "chCheckServer" ), 
		( df.INFO, "0", None, None, "chInfo" ),
		( df.SHOW_LOG, "?", None, None, "chShowLog" ),
		( df.VERSION, "?", None, {df.SERVER_SIDE}, "chVersion" ),
		( df.REPORT, "1+", None, None, "chReport" ) )
	
	def __init__( self ):
		super( Info, self).__init__()
		self.info = {}

		self.info["general"] = {}
		self.timestarted = datetime.now()

		Info.registerGroupHandlers( self.processCmd )
		
	# Command handlers

	def chCheckServer( self, cmd ):
		'''Check regd server'''
		resp = "Up and running since {0}\nUptime:{1}.".format( 
			str( self.timestarted ).rpartition( "." )[0],
			str( datetime.now() - self.timestarted ).rpartition( "." )[0] )
		return composeResponse( '1', resp )


	def chInfo( self, cmd ):
		'''Report server information'''
		# pylint: disable=unused-variable
		accl = getShared( "accLevel" )
		dfile = getShared( "dataFile" )
		sfile = getShared( "sockFile" )

		resp = "{0} : {1}\n".format( app.APPNAME, df.__description__ )
		resp += "License: {0}\n".format( df.__license__ )
		resp += "Homepage: {0}\n\n".format( df.__homepage__ )
		resp += "Server version: {0}\n".format( df.rversion )
		resp += "Server datafile: {0}\n".format( dfile )
		resp += "Server access: {0}\n".format( accl )
		resp += "Server socket file: {0}\n".format( sfile )

		return composeResponse( "1", resp )

	def chShowLog( self, cmd ):
		'''Show server log'''
		par = cmd["params"]
		n = 20
		if par:
			try:
				n = int( par[0] )
			except ValueError:
				raise IKException( ErrorCode.unrecognizedParameter, par[0],
					moreInfo = "Number of lines only must contain digits." )
		return composeResponse( '1', util.getLog( n ) )

	def chVersion( self, cmd ):
		'''Return regd version.'''
		return composeResponse( '1', "Regd server version: " + df.__version__ )

	def chReport( self, cmd ):
		'''Report server variables.'''
		par = cmd["params"][0]
		retCode = '1'
		if par == df.ACCESS:
			resp = "{0}".format( self.srv.acc )
		elif par == df.REP_STORAGE:
			path = None
			if len( cmd["params"] ) > 1:
				if len( cmd["params"] == 2 ):
					path = cmd["params"][1]
				else:
					raise IKException( ErrorCode.unrecognizedSyntax, " ".join( cmd["params"] ) )
			resp = self.fs.stat( path )
		elif par == df.REP_SERVER:
			# TODO:
			bs = getShared( "bytesSent" )
			br = getShared( "bytesReceived" )
			resp = "Bytes sent: {0}\n".format( bs )
			resp += "Bytes received: {0}\n".format( br )
		elif par == df.REP_COMMANDS:
			resp = util.printMap( self.info["cmd"], 0)
			pass
		elif par == df.DATAFILE:
			resp = self.fs.datafile
		else:
			retCode = '0'
			resp = "Unrecognized command parameter: " + par

		return composeResponse( retCode, resp )

def setShared( nam, val, mode=None ):
	'''Assign value to internal shared data.'''
	"Returns json packet"
	tok = "{0}={1}".format( util.joinPath( "/_sys", nam ), val )
	cmd = { "cmd": df.ADD_TOKEN, "params": [tok], "internal": True }
	if mode == df.FORCE:
		cmd[df.FORCE] = True
	elif mode == df.SUM:
		cmd[df.SUM] = True
	ret = CmdSwitcher.switchCmd( cmd )
	if cmd['res'] == 0:
		ret = util.parsePacket( ret )
		#log.error( "Set shared data '%s' failed: %s" % ( nam, l[1] ) )
		raise IKException( ErrorCode.programError, ret[1] )
	

def getShared( nam ):
	tok = util.joinPath( "/_sys", nam )
	cmd = { "cmd": df.GET_ITEM, "params": [tok], "internal": True }
	ret = CmdSwitcher.switchCmd( cmd )
	ret = util.parsePacket( ret )
	if cmd['res'] == 0:
		raise IKException( ErrorCode.programError, ret[1] )

	return ret[1]

