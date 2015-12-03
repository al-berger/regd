'''********************************************************************
*	Package:       tests
*	
*	Module:        dtests.py
*
*	Created:	   2015-Nov-30 07:50:25 PM
*
*	Abstract:	   Develop tests for regd. 
*
*	Copyright:	   Albert Berger, 2015.
*
*********************************************************************'''
__lastedited__ = "2015-12-02 05:18:38"

import os, tempfile, unittest, logging, time
import regd.defs as defs
from regd.tok import TokenFeeder
import regd.testing.test_help as th, regd.testing.tests as tests

rc = "regd" # 'regd' command

class globInit():
	def __init__(self):
		# Setting up logging
		global log, currentTest
				
		log = logging.getLogger("dtests")
		logl = logging.INFO
	
		log.setLevel(logl)
	
		strlog = logging.StreamHandler()
		strlog.setLevel( logl )
		bf = logging.Formatter( "[{funcName:s} : {message:s}", "", "{" )
		strlog.setFormatter( bf )
		log.addHandler( strlog )
		


class SerdataTest(unittest.TestCase):

	def runTest(self):
		'''Datafiles and serialization.'''
		tmpdirobj = tempfile.TemporaryDirectory( prefix="regd.tmp." )
		tmpdir = tmpdirobj.name
		with open( os.path.join(os.path.dirname(__file__), "serdata"), "rb"  ) as f:
			s = f.read()
		fdata = s.split(b'.')
		for i in range(0,3):
			with open(os.path.join(tmpdir, "file{0}".format(i+1)), "wb") as f:
				f.write(fdata[i])
		treg = th.TestReg(rc, servName="dfiletest", datafile=os.path.join(tmpdir, "file1"), 
						loglevel="WARNING")
		treg.create()
		tf = TokenFeeder(parts=[x.decode() for x in fdata[5].split(b'\n') if x],
							bparts=[x for x in fdata[5].split(b'\n') if x])
		log.info("\nChecking tokens added to server...")
		tf.setMode(TokenFeeder.modeKeyVal)
		self.assertTrue( treg.compare( defs.GET_TOKEN, tf, binary=False, fb=tests.PrintDot( 10 ) ),
				"Failed comparing tokens in registry {0} with original values.".format( 
				treg.servName ) )
		log.info( "\n%i tokens were checked." % ( len( tf ) ) )
		secpath = "/sav/f1sec2/file2/file3/f3sec1/QQQQ"
		tok = secpath + "=PPPP"
		treg.sendCmd( defs.ADD_TOKEN, tok )
		treg.sendCmd( defs.SETATTR, secpath, "--attrs",	"persPath=QQQQ")
		log.info("Stopping server.")
		treg.sendCmd( defs.STOP_SERVER )
		time.sleep(2)
		log.info("Starting server.")
		treg.create() 
		res, ret = treg.sendCmd( defs.GET_TOKEN, secpath )
		self.assertTrue( res and ret == "PPPP")		
		
		tmpdirobj.cleanup()
	
	
globinit = globInit()
# Setting up test
currentTest = unittest.TestSuite()
currentTest.addTest(SerdataTest())

if __name__ == "__main__":
	unittest.main(verbosity=2,defaultTest = currentTest)
	
	
	