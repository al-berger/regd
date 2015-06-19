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

__lastedited__ = "2015-06-18 16:50:34"

import unittest, time
import subprocess as sp
import regdcmd  # @UnresolvedImport

regd = "../regd/regd.py"
serverName = "test"
username = None
	

class BasicTest(unittest.TestCase):
	def setUp(self):
		pass

	def tearDown(self):
		pass

	@classmethod
	def setUpClass(cls):
		sp.Popen( [regd, "--start", "--server-name", serverName ] )
		time.sleep( 1 )

	@classmethod
	def tearDownClass(cls):
		sp.Popen( [regd, "--stop", "--server-name", serverName ] )


	def testAdd(self):
		try:
			res = sp.check_output( [regd, "--server-name", serverName, "--add", "aaa=bbb" ] )
		except sp.CalledProcessError as e:
			print( regd, "--add returned non-zero: ", e.output )
				
		self.assertEqual(res, b"1\n")
		try:
			res = sp.check_output( [regd, "--server-name", serverName, "--get", "aaa" ] )
		except sp.CalledProcessError as e:
			print( regd, "--get returned non-zero: ", e.output )
		self.assertEqual(res, b"1bbb\n")
		


if __name__ == "__main__":
	#import sys;sys.argv = ['', 'Test.testName']
	unittest.main()