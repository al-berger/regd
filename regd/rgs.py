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

__lastedited__ = "2015-12-23 21:02:28"

import signal
import regd.serv as serv
import regd.info as info
import regd.cmds as cmds
import regd.fs as fs
import regd.defs as defs
from regd.util import log
from regd.app import IKException, ErrorCode, sigHandler, ROAttr, glSignal

class Registry():
	'''Registry'''
	def __init__(self, ):
		"""TODO: to be defined1. """
		
# The regd registry server process contains three permanently running threads:
# - startRegistry function : main
# - srv : server
# - fs : storage
# The main thread listens for signals and performs graceful shutdown when a signal is
# received.
# The server thread is blocking in socket listening and is interrupted from block by
# setting the 'cont' variable to False and closing the socket.
# The storage thread is blocking in waiting for condition with timeout between regular 
# awakenings for maintenance and is interrupted from block by setting the 'cont' variable
# to False and condition notifying.  

def startRegistry( servername, sockfile = None, host = None, port = None, acc = defs.PL_PRIVATE, 
		datafile = None, binsecfile = None ):
	srv = connStor = None
	
	def shutdown():
		nonlocal srv, connStor
		# Stopping the server
		srv.cont = False
		srv.sock.close()
		srv.close()
		# Stopping the storage
		connStor.close()
		
	def signal_handler( signal, frame ):
		shutdown()
		
	sigHandler.push( signal.SIGINT, signal_handler )
	sigHandler.push( signal.SIGTERM, signal_handler )
	sigHandler.push( signal.SIGHUP, signal_handler )
	sigHandler.push( signal.SIGABRT, signal_handler )
	sigHandler.push( signal.SIGALRM, signal_handler )
	
	try:				
		# Server
		log.debug( "Creating server instance")
		srv = serv.RegdServer( servername, sockfile, host, port, acc )
		# Storage
		log.debug( "Creating storage")
		connStor = fs.startStorage( datafile, binsecfile )
		# Info
		log.debug( "Creating info")
		info.Info( )
		log.debug( "Starting server")
		srv.start_loop()
	except Exception as e:
		log.error( "Failed to start server: {0}".format( e ) )
	else:
		glSignal.acquire()
		# Wait till notification on df.SERVER_STOP 
		glSignal.wait()
		shutdown()


		
