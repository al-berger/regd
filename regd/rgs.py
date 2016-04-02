"""******************************************************************
*	Module:			regd
*	
*	File name:		rgs.py
*
*	Created:		2015-12-19 09:53:54
*
*	Abstract:		Registry.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*******************************************************************"""

__lastedited__ = "2016-04-02 10:01:33"

import signal
import regd.serv as serv
import regd.info as info
import regd.cmds as cmds
import regd.fs as fs
import regd.defs as defs
from regd.util import log
from regd.appsm.app import IKException, ErrorCode, sigHandler, ROAttr, glSignal

class Registry():
	'''Registry'''
	def __init__(self, ):
		"""TODO: to be defined1. """
		
# The regd registry consists of two permanently running processes:
# - srv : server
# - fs : storage
# and temporary processes created for handling incoming server commands.
#
# The server thread is blocking in socket listening and is interrupted from block by
# setting the 'cont' variable to False and closing the socket.
# The storage thread is blocking in waiting for condition with timeout between regular 
# awakenings for maintenance and is interrupted from block by setting the 'cont' variable
# to False and condition notifying.  

def startRegistry( servername, sockfile = None, host = None, port = None, acc = defs.PL_PRIVATE, 
		datafile = None, binsecfile = None ):
	srv = connStor = None
	
	def shutdown():
		log.info("Registry is shutting down...")
		cmds.CmdSwitcher.switchCmd( { "cmd" : fs.FS_STOP } )
		log.info( "Shutdown complete." )
		
	def signal_handler( signal, frame ):
		#shutdown()
		# Returning normally, so that the signal notification be forwarded to
		# the wakeup socket.
		return
		
	sigHandler.push( signal.SIGINT, signal_handler )
	sigHandler.push( signal.SIGTERM, signal_handler )
	sigHandler.push( signal.SIGHUP, signal_handler )
	sigHandler.push( signal.SIGABRT, signal_handler )
	sigHandler.push( signal.SIGALRM, signal_handler )
	
	try:				
		# Storage
		log.debug( "Creating storage")
		connStor, sigStor = fs.startStorage( acc, datafile, binsecfile )
		# Server
		log.debug( "Creating server instance")
		srv = serv.RegdServer( servername, sockfile, host, port, acc )
		# Info
		log.debug( "Creating info")
		info.Info( )
		log.debug( "Starting server")
		srv.start_loop( sigStor )
	except Exception as e:
		log.error( "Failed to start server: {0}".format( e ) )
	else:
		#glSignal.acquire()
		# Wait till notification on df.SERVER_STOP 
		#glSignal.wait()
		shutdown()
		log.info( "Exiting." )


		
