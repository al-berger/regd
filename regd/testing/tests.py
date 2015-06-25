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
__lastedited__ = "2015-06-25 17:14:39"

import unittest, sys, os, pwd, logging, re
from configparser import ConfigParser
from regd.testing import test_help as th
test_basic = False
test_network = False
test_multiuser = False
tregs = None
ntregs = None
mtregs = None
cp = None
log = None

currentTest = None


# As of Python 3.4.3, setting globals in setUpModule doesn't succeed
class globInit():
	def __init__(self):
		global cp, log, test_basic, test_network, test_multiuser, tregs, ntregs, mtregs
		global currentTest
		
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
			
		loglevel = cp["general"].get("loglevel", "1")
		
		log = logging.getLogger("tests")
		if loglevel == '2':
			logl = logging.INFO
		elif loglevel == '3':
			logl = logging.DEBUG
		else:
			logl = logging.CRITICAL
		
		log.setLevel(logl)
		loglevelname = logging.getLevelName(logl)
	
		strlog = logging.StreamHandler()
		strlog.setLevel( logl )
		bf = logging.Formatter( "[{funcName:s} : {message:s}", "", "{" )
		strlog.setFormatter( bf )
		log.addHandler( strlog )
		
		th.setLog( logging.ERROR )
		
		tryVerbose = ( "Try to configure and run this test with VERBOSE output" 
						" level for more information.")
		runConfigure = ( "\nPlease run 'regd --test-configure'.\n\nExiting.")
				
		tregs = []

		# Setting up test
		currentTest = unittest.TestSuite()
		currentTest.addTest(TokensTest())
		
		testtype = cp["general"].get("test_type", "1")
		
		if testtype == '1':
			test_basic = True
			tregs = th.filesocket_setup(loglevelname, None)
			if not len(tregs):
				print("Error: could not start BASIC test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()
			
			currentTest.addTest(BasicPermissionTest())
			print("\nStarting BASIC test.")
					
		elif testtype == '2':
			test_network = True
			host = cp["general"].get("host", None)
			if not host or not re.match( "[a-zA-Z0-9\.-]+", host ):
				print(( "Error: host name is not specified or invalid: '{0}'.{1}").format(
																host, runConfigure))
				errorExit()
			port = cp["general"].get("port", None)
			if not port or not re.match("[0-9]+", port) or int(port) > 65536:
				print(( "Error: port number is not specified or invalid: '{0}'.{1}").format(
																port, runConfigure))
				errorExit()
				
			nsids = [(host, port)]
			ntregs = th.network_setup(nsids, loglevelname, None)
			if not len(ntregs):
				print("Error: could not start NETWORK test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()
			
			print("\nStarting NETWORK test.")
			
		elif testtype == '3':
			test_multiuser = True
			multiuser = cp["general"].get("multiuser", None)
			if not multiuser:
				print("Error: no server side user account is specified.{1}".format(runConfigure))
				errorExit()
			try:
				pwd.getpwnam( multiuser ).pw_uid
			except KeyError:
				print(("Error: server side user account with name '{0}' is not present"
					" on this system. {1}").format(multiuser, runConfigure ))
				errorExit()
				
			mtregs = th.multiuser_setup(multiuser, loglevelname, None)
			if not len(mtregs):
				print("Error: could not start MULTIUSER test.")
				if loglevel == "1":
					print( tryVerbose )
				errorExit()
				
			currentTest.addTest(MultiuserPermissionTest())
			print("\nStarting MULTIUSER test.")
		

def setUpModule():
	pass

def tearDownModule():
	if test_basic:
		th.filesocket_finish()
	if test_network:
		th.network_finish()

def errorExit(code=-1):
	tearDownModule()
	sys.exit(code)

class PrintDot:
	def __init__(self, num):
		self.num = num
		self.cnt = 0

	def __call__(self):
		if self.cnt % self.num == 0:
			print(".", end='', flush=True)
		self.cnt += 1

class TokensTest(unittest.TestCase):
	'''Checking correct handling of various character combinations in various token parts.'''
	tregs = []
		
	def __init__(self, methodName='runTest'):
		self.longMessage = False
		super(TokensTest, self).__init__("runTest")
			
	@classmethod
	def setUpClass(cls):
		super(TokensTest, cls).setUpClass()
		print("\nStarting testing token operations.")
		if test_basic:
			cls.tregs.append( tregs[0] )
		if test_network:
			cls.tregs.append( ntregs[0] )
		if test_multiuser:
			cls.tregs.append( mtregs[0] )
			
	# Testing tokens contents

	def testAdd(self):
		print("\nTesting adding tokens to server...")
		tf = th.TokenStringFeeder( th.testtokens )

		for treg in self.tregs:
			self.assertTrue( treg.do_token_cmd( "--add", tf, PrintDot(10) ), 
				"Failed adding tokens to registry {0}.".format( treg.servName ) )
		log.info( "\n%i tokens were added." % ( len( tf ) ) )
		
	def testCompare(self):
		print("\nChecking tokens added to server...")
		cf = th.ChecksFeeder( th.testtokens )
		for treg in self.tregs:
			self.assertTrue( treg.compare( "--get", cf, PrintDot(10) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )
		log.info( "\n%i tokens were checked." % ( len( cf ) ) )
			
	def testRemove(self):
		print("\nTesting removing tokens from server...")
		tk = th.KeysFeeder( th.testtokens )
		for treg in self.tregs:
			self.assertTrue( treg.do_token_cmd( "--remove", tk, PrintDot(10) ),
						"Failed removing tokens from registry {0}.".format( treg.servName ) )
		log.info( "\n%i tokens were removed." % ( len( tk ) ) )
		
	# Testing sections
	
	def testRemoveSections(self):
		pass
		
	def runTest(self):
		self.testAdd()
		self.testCompare()
		self.testRemove()


#@unittest.skipUnless(test_basic, "Skipping basic file socket permission test.")
class BasicPermissionTest(unittest.TestCase):
	'''Test permission levels.'''
		
	def __init__(self, methodName="runTest"):
		super(BasicPermissionTest, self).__init__()
		self.longMessage = False
		
	@classmethod
	def setUpClass(cls):
		super(BasicPermissionTest, cls).setUpClass()
		print("\nStarting testing permissions.")
		
	def testBasic(self):
		log.info("Performing permissions tests...")
		for treg in tregs:
			self.assertTrue( treg.checkToken("a", "b", "c") )
		log.info("Done.")
		
	def runTest(self):
		self.testBasic()

#@unittest.skipUnless(test_multiuser, "Skipping multiuser file socket permission test.")
class MultiuserPermissionTest(unittest.TestCase):
	'''Test permission levels.'''
		
	def __init__(self, methodName="runTest"):
		super(MultiuserPermissionTest, self).__init__()
		self.longMessage = False
		
	@classmethod
	def setUpClass(cls):
		super(MultiuserPermissionTest, cls).setUpClass()
		print("\nStarting testing permissions.")
			
	def testMultiuser(self):
		log.info("Performing permissions tests...")
		testkey = th.toksections[0] + ":" + th.toknames[0]
		for treg in mtregs:
			if treg.acc == "private" or not treg.acc:
				self.assertFalse( treg.sendCmd("--add" "a=b"), 
								"Failed to check private access for --add command.")
				self.assertFalse( treg.sendCmd("--get", testkey), 
								"Failed to check private access for --get command.")
				self.assertFalse( treg.sendCmd("--remove", testkey), 
								"Failed to check private access for --remove command.")
		log.info("Done.")
		
	def runTest(self):
		self.testMultiuser()



gi = globInit()	
	
if __name__ == "__main__":
	unittest.main(verbosity=2,defaultTest = currentTest)