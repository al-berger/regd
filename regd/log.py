'''*****************************************************************
*	Module:			log
*
*	Created:		Dec 7, 2015
*
*	Abstract:		Log handler for standard logging module.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*
*****************************************************************'''
__lastedited__ = "2015-12-08 02:31:51"

import sys, os, logging
import regd.comm as comm

try:
	PROCNAME = os.path.basename( sys.modules['__main__'].__file__ ).partition(".")[0]
except:
	# Can be imported from console __main__, without __file__ attribute
	PROCNAME = "console"
	pass

class RegdHandlerLog( logging.StreamHandler ):
	def __init__(self, servAddr, name=PROCNAME ):
		'''tokPath - address of a bin token'''
		super(RegdHandlerLog, self).__init__()
		self.rcom = comm.RegdComm( servAddr=servAddr )
		self.name = name
	
	def handle(self, record):
		self.rcom.logMessage( self.name, record.getMessage() )
			
class RegdHandlerNotify( logging.StreamHandler ):
	def __init__(self, servAddr, name=PROCNAME, tokPath=None):
		super(RegdHandlerNotify, self).__init__()
		self.rcom = comm.RegdComm( servAddr=servAddr )
		self.name = name
		self.tokPath = tokPath
	
	def handle(self, record):
		level = record.levelno
		icon = "dialog-error"
		tm = 0
		if level <= logging.INFO:
			icon = "dialog-information"
			tm = 10000
		elif level < logging.ERROR:
			icon = "dialog-warning"
			tm = 30000
		
		msg = "-t {0} --icon={1} '{2}' '{3}'".format( 
											tm, icon, self.name, record.getMessage() )
		#print("regd handler:", self.tokPath, msg,)
		self.rcom.addToken( self.tokPath, msg )
		
		
		