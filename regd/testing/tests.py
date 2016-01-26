'''********************************************************************
*	Package:       tests
*
*	Module:        tests.py
*
*	Created:	   2015-Jun-18 12:20:25 PM
*
*	Abstract:	   Tests for regd.
*
*	Copyright:	   Albert Berger, 2015.
*
*********************************************************************'''
__lastedited__ = "2016-01-26 11:27:51"

import unittest, sys, os, pwd, logging, re, time
from configparser import ConfigParser
from regd.testing import test_help as th
import regd.defs as defs
import regd.tok as tok
test_basic = False
test_network = False
test_multiuser = False
tregs = None
ntregs = None
mtregs = None
cp = None
log = None
loglevelname = None

currentTest = None


# As of Python 3.4.3, setting globals in setUpModule() doesn't succeed
class globInit():
	def __init__( self ):
		global cp, log, test_basic, test_network, test_multiuser, tregs, ntregs, mtregs
		global currentTest, loglevelname

		username = pwd.getpwuid( os.getuid() )[0]
		homedir = None
		if username:
			homedir = os.path.expanduser( '~' + username )
		if not homedir:
			tstconf = None
		else:
			# Reading test.conf file
			tstconf = homedir + "/.config/regd/test.conf"
			if not os.path.exists( tstconf ):
				tstconf = None

		# Reading test configuration

		cp = ConfigParser()
		if tstconf:
			cp.read( tstconf )

		if not cp.has_section( "general" ):
			cp.add_section( "general" )

		# Setting up logging

		loglevel = cp["general"].get( "loglevel", "1" )

		log = logging.getLogger( "tests" )
		if loglevel == '2':
			logl = logging.INFO
		elif loglevel == '3':
			logl = logging.DEBUG
		else:
			logl = logging.CRITICAL

		log.setLevel( logl )
		loglevelname = logging.getLevelName( logl )

		strlog = logging.StreamHandler()
		strlog.setLevel( logl )
		bf = logging.Formatter( "[{funcName:s} : {message:s}", "", "{" )
		strlog.setFormatter( bf )
		log.addHandler( strlog )

		th.setLog( logging.ERROR )

		tryVerbose = ( "Try to configure and run this test with VERBOSE output"
						" level for more information." )
		runConfigure = ( "\nPlease run 'regd test-configure'.\n\nExiting." )

		tregs = []

		# Setting up test
		currentTest = unittest.TestSuite()
		currentTest.addTest( TokensTest() )
		currentTest.addTest( FilesTest() )

		testtype = cp["general"].get( "test_type", "1" )

		if testtype == '1':
			test_basic = True
			'''tregs = th.filesocket_setup(loglevelname, None)
			if not len(tregs):
				print("Error: could not start BASIC test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()'''

			currentTest.addTest( BasicPermissionTest() )
			print( "\nStarting BASIC test." )

		elif testtype == '2':
			test_network = True
			host = cp["general"].get( "host", None )
			if not host or not re.match( "[a-zA-Z0-9\.-]+", host ):
				print( ( "Error: host name is not specified or invalid: '{0}'.{1}" ).format( 
																host, runConfigure ) )
				errorExit()
			port = cp["general"].get( "port", None )
			if not port or not re.match( "[0-9]+", port ) or int( port ) > 65536:
				print( ( "Error: port number is not specified or invalid: '{0}'.{1}" ).format( 
																port, runConfigure ) )
				errorExit()

			nsids = [( host, port )]
			'''ntregs = th.network_setup(nsids, loglevelname, None)
			if not len(ntregs):
				print("Error: could not start NETWORK test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()'''

			print( "\nStarting NETWORK test." )

		elif testtype == '3':
			test_multiuser = True
			multiuser = cp["general"].get( "multiuser", None )
			if not multiuser:
				print( "Error: no server side user account is specified.{1}".format( runConfigure ) )
				errorExit()
			try:
				pwd.getpwnam( multiuser ).pw_uid
			except KeyError:
				print( ( "Error: server side user account with name '{0}' is not present"
					" on this system. {1}" ).format( multiuser, runConfigure ) )
				errorExit()

			'''mtregs = th.multiuser_setup(multiuser, loglevelname, None)
			if not len(mtregs):
				print("Error: could not start MULTIUSER test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()'''

			currentTest.addTest( MultiuserPermissionTest() )
			print( "\nStarting MULTIUSER test." )


def setUpModule():
	pass

def tearDownModule():
	if test_basic:
		th.filesocket_finish()
	if test_network:
		th.network_finish()

def errorExit( code = -1 ):
	tearDownModule()
	sys.exit( code )

class PrintDot:
	def __init__( self, num ):
		self.num = num
		self.cnt = 0

	def __call__( self ):
		if self.cnt % self.num == 0:
			print( ".", end = '', flush = True )
		self.cnt += 1

class TokensTest( unittest.TestCase ):
	'''Checking correct handling of various character combinations in various token parts.'''

	def __init__( self, methodName = 'runTest' ):
		self.longMessage = False
		super( TokensTest, self ).__init__( "runTest" )

	# Testing tokens contents

	def runTest( self ):
		log.info( "\nStarting testing token operations." )
		tregs = th.filesocket_setup( ["tst"], ["private"], loglevelname, None )
		tf = th.TstTokenFeeder( th.testParts, th.btestParts, 5 )
		time.sleep( 3 )

		log.info( "\nTesting adding tokens to server..." )
		for treg in tregs:
			self.assertTrue( treg.do_token_cmd( defs.ADD_TOKEN, tf, fb = PrintDot( 10 ) ),
				"Failed adding tokens to registry {0}.".format( treg.servName ) )
		log.info( "\n%i tokens were added." % ( len( tf ) ) )

		log.info( "\nChecking tokens added to server..." )
		tf.setMode( tok.TokenFeeder.modeKeyVal )
		for treg in tregs:
			self.assertTrue( treg.compare( defs.GET_ITEM, tf, binary = False, fb = PrintDot( 10 ) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )
		log.info( "\n%i tokens were checked." % ( len( tf ) ) )

		log.info( "\nTesting removing tokens from server..." )
		tf.setMode( tok.TokenFeeder.modeKey )
		for treg in tregs:
			self.assertTrue( treg.do_token_cmd( defs.REMOVE_TOKEN, tf, fb = PrintDot( 10 ) ),
						"Failed removing tokens from registry {0}.".format( treg.servName ) )
		log.info( "\n%i tokens were removed." % ( len( tf ) ) )
		th.filesocket_finish( ["tst"] )

class FilesTest( unittest.TestCase ):

	def __init__( self, methodName = 'runTest' ):
		self.longMessage = False
		super( FilesTest, self ).__init__( "runTest" )

	# Testing tokens contents

	def runTest( self ):
		log.info( "\nStarting testing file handling." )
		tregs = th.filesocket_setup( ["tst"], ["private"], loglevelname, None )
		time.sleep( 3 )
		tf = tok.TokenFeeder( th.datafile_tokens )
		tf.setMode( tok.TokenFeeder.modeKeyVal )

		# s = input("Server started")

		# Upon starting the server should contain tokens from the 'datafile_lines'
		for treg in tregs:
			self.assertTrue( treg.compare( defs.GET_ITEM, tf, binary = False,
								cmdOpts = [( defs.PERS, None )], fb = PrintDot( 10 ) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )

		# s = input("Tokens checked")

		# Adding some new persistent tokens
		tf1 = th.TstTokenFeeder( th.testParts, th.btestParts, 5 )
		for treg in tregs:
			self.assertTrue( treg.do_token_cmd( defs.ADD_TOKEN, tf1,
											cmdOpts = [( defs.PERS, None )], fb = PrintDot( 10 ) ),
											"Failed to add tokens to registry." )

		s = input( "File test: New tokens added." )

		# Restarting server
		tregs = th.filesocket_setup( ["tst"], ["private"], loglevelname, None, useDataFile = True )

		s = input( "File test: server restarted" )

		# Upon starting the server should contain tokens from the 'datafile_lines' and
		# newly added tokens

		for treg in tregs:
			self.assertTrue( treg.compare( defs.GET_ITEM, tf, binary = False,
								cmdOpts = [( defs.PERS, None )], fb = PrintDot( 10 ) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )
			s = input( "File test: datafile tokens checked." )
			tf1.setMode( tok.TokenFeeder.modeKeyVal )
			self.assertTrue( treg.compare( defs.GET_ITEM, tf1, binary = False,
								cmdOpts = [( defs.PERS, None )], fb = PrintDot( 10 ) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )
			s = input( "File test: test tokens checked." )


# @unittest.skipUnless(test_basic, "Skipping basic file socket permission test.")
class BasicPermissionTest( unittest.TestCase ):
	'''Test permission levels.'''

	def __init__( self, methodName = "runTest" ):
		super( BasicPermissionTest, self ).__init__()
		self.longMessage = False

	@classmethod
	def setUpClass( cls ):
		super( BasicPermissionTest, cls ).setUpClass()
		print( "\nStarting testing permissions." )

	def testBasic( self ):
		log.info( "Performing permissions tests..." )
		for treg in tregs:
			self.assertTrue( treg.checkToken( "a", "b", "c" ) )
		log.info( "Done." )

	def runTest( self ):
		self.testBasic()

# @unittest.skipUnless(test_multiuser, "Skipping multiuser file socket permission test.")
class MultiuserPermissionTest( unittest.TestCase ):
	'''Test permission levels.'''

	def __init__( self, methodName = "runTest" ):
		super( MultiuserPermissionTest, self ).__init__()
		self.longMessage = False

	@classmethod
	def setUpClass( cls ):
		super( MultiuserPermissionTest, cls ).setUpClass()
		print( "\nStarting testing permissions." )

	def testMultiuser( self ):
		log.info( "Performing permissions tests..." )
		testkey = th.toksections[0] + ":" + th.toknames[0]
		for treg in mtregs:
			if treg.acc == "private" or not treg.acc:
				self.assertFalse( treg.runCmd( "add" "a=b" ),
								"Failed to check private access for --add command." )
				self.assertFalse( treg.runCmd( "get", testkey ),
								"Failed to check private access for --get command." )
				self.assertFalse( treg.runCmd( "remove", testkey ),
								"Failed to check private access for --remove command." )
		log.info( "Done." )

	def runTest( self ):
		self.testMultiuser()



gi = globInit()

if __name__ == "__main__":
	unittest.main( verbosity = 2, defaultTest = currentTest )
