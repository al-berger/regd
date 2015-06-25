#!/usr/bin/env python3
'''********************************************************************
*	Package:       tests
*	
*	Module:        test_help.py
*
*	Created:	   2015-Jun-18 13:20:25 PM
*
*	Abstract:	   Testing helpers: classes and routines. 
*
*	Copyright:	   Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__ = "2015-06-25 15:15:18"


import sys, os, socket, argparse, logging, time, re, pwd
import subprocess as sp
from configparser import ConfigParser
# import regd
from regd import regd

log = None
tstconf = None

def setLog( loglevel, logtopics = None ):
	global log, logtok
	log = logging.getLogger( "tests" )

	log.setLevel( loglevel )

	# Console output
	strlog = logging.StreamHandler()
	strlog.setLevel( loglevel )
	bf = logging.Formatter( "[{funcName:s} : {message:s}", "", "{" )
	strlog.setFormatter( bf )
	log.addHandler( strlog )



def regdcmd( cmd = None, data = None, servername = None, host = None, port = None ):
	if host:
		# Create an Internet socket
		sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	else:
		# Create a UDS socket
		sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )

		try:
			atuser, servername = regd.parse_server_name( servername )
		except regd.ISException as e:
			print( e )
			return e.code

		_, sockfile = regd.get_filesock_addr( atuser, servername )


	if cmd and ( cmd.find( "_sec " ) != -1 or cmd.endswith( "_sec" ) ):
		# Time to enter the password
		sock.settimeout( 30 )
	else:
		sock.settimeout( 3 )

	try:
		if host:
			sock.connect( ( host, port ) )
		else:
			sock.connect( sockfile )
	except OSError as er:
		print( "Socket error %d: %s\nServer address: %s",
				er.errno, er.strerror, sockfile )
		return False, 0

	res = False

	try:
		# Send data
		if cmd:
			if cmd.startswith( "--" ):
				cmd = cmd[2:]
			cmd = cmd.replace( '-', '_' )
			if not cmd.startswith( regd.CMDMARKER ):
				cmd = regd.CMDMARKER + cmd

			data = cmd + ' ' + data

		bPacket = bytearray( data + regd.EODMARKER, encoding = 'utf-8' )

		sock.sendall( bPacket )

		data = bytearray()
		eodsize = len( regd.EODMARKER )
		# Format of the response packet: <4b: packet length><4b: response code>[data]
		while True:
			data.extend( sock.recv( 4096 ) )
			datalen = len( data )
			if datalen >= eodsize and data[-eodsize:].decode( 'utf-8' ) == regd.EODMARKER:
				break

		data = data[:-eodsize].decode( 'utf-8' )

		# res = struct.unpack_from("L", data, offset=0)[0]

		sock.shutdown( socket.SHUT_RDWR )
		sock.close()

		if data[0] != '1':
			res = False
		else:
			res = True
		ret = data[1:]
	except OSError:
		pass
	finally:
		try:
			sock.shutdown( socket.SHUT_RDWR )
			sock.close()
		except:
			pass

	return res, ret

rc = os.path.dirname( __file__ ).rpartition( '/' )[0] + "/regd.py"

sn = "--server-name"
add = "--add"

def clp( s ):
	return( "--" + s.replace( "_", "-" ) )

testtokens = [
"\\",
"\\:",
"= \\:",
":= \\: \\",
"\\::= \\: \\==",
"[={(\\)}::]",
"<{}()(<>][]",
"\"Quoted\"",
"\"'\"\"'' ' \"",
"`~!@#$%^&*()-_=+\\/|><,.:",
"фжÅ»«ЭФ¿¡Ц¨¶щцяЮб"
]

toksections = [
"section1",
"section2",
"section3"
]

toknames = [
"name1",
"name2",
"name3"
]

tokvalues = [
"value1",
"value2",
"value3"
]


class TokenFeeder:
	def __init__( self, sec, nam = None, val = None, num = None ):
		self.sec = sec
		self.nam = nam if nam else self.sec
		self.val = val if val else self.sec
		self.cnt = 0
		self.num = num if num != None and num < self.__len__() and num > 0 else self.__len__()

	def __iter__( self ):
		return self

	def __len__( self ):
		return len( self.sec ) * len( self.nam )

	def __next__( self ):
		if self.cnt >= self.len:
			raise StopIteration()
		si = self.cnt // len( self.sec )
		ni = self.cnt % len( self.nam )
		s = self.sec[si]
		n = self.nam[ni]
		v = self.val[si]
		cur = "{0}-{1}-{2} ({3})".format( si, ni, si, self.cnt )
		self.cnt += 1
		return ( ( s, n, v ), cur )

	def reset( self ):
		self.cnt = 0

	def getToken( self, si, ni, vi ):
		return ( self.sec[si], self.nam[ni], self.val[vi] )

class TokenStringFeeder( TokenFeeder ):
	def __init__( self, sec, nam = None, val = None, num = None ):
		super( TokenStringFeeder, self ).__init__( sec, nam, val, num )

	def __next__( self ):
		if self.cnt >= self.__len__():
			raise StopIteration()
		si = self.cnt // len( self.sec )
		ni = self.cnt % len( self.nam )
		s = self.sec[si].replace( ":", "\:" )
		n = self.nam[ni].replace( "=", "\=" )
		if s[-1] == '\\': s += ' '
		if n[-1] == '\\': n += ' '
		tok = "{0}:{1}={2}".format( s, n, self.val[si] )
		cur = "{0}-{1}-{2} ({3})".format( si, ni, si, self.cnt )
		self.cnt += 1
		return ( tok, cur )

class ChecksFeeder( TokenFeeder ):
	def __init__( self, sec, nam = None, val = None, num = None ):
		super( ChecksFeeder, self ).__init__( sec, nam, val, num )

	def __next__( self ):
		if self.cnt >= self.__len__():
			raise StopIteration()
		si = self.cnt // len( self.sec )
		ni = self.cnt % len( self.sec )
		s = self.sec[si].replace( ":", "\:" )
		if s[-1] == '\\': s += ' '
		checkkey = "{0}:{1}".format( s, self.nam[ni], self.val[si] )
		checkval = self.val[si]
		cur = "{0}-{1}-{2} ({3})".format( si, ni, si, self.cnt )
		self.cnt += 1
		return ( checkkey, checkval, cur )

class KeysFeeder( TokenFeeder ):
	def __init__( self, sec, nam = None, num = None ):
		super( KeysFeeder, self ).__init__( sec, nam = nam, num = num )

	def __next__( self ):
		if self.cnt >= self.__len__():
			raise StopIteration()
		si = self.cnt // len( self.sec )
		ni = self.cnt % len( self.sec )
		s = self.sec[si].replace( ":", "\:" )
		if s[-1] == '\\': s += ' '
		checkkey = "{0}:{1}".format( s, self.nam[ni], self.val[si] )
		cur = "{0}-{1} ({2})".format( si, ni, self.cnt )
		self.cnt += 1
		return ( checkkey, cur )

def compose_tokens( l, res ):
	for i in range( 0, len( l ) ):
		s = l[i].replace( ":", "\:" )
		for k in range( 0, len( l ) ):
			n = l[k].replace( "=", "\=" )
			res.append( "{0}:{1}={2}".format( s, n, l[i] ) )

def compose_checks( checks, reskeys, resvals ):
	for i in range( 0, len( checks ) ):
		s = checks[i].replace( ":", "\:" )
		for k in range( 0, len( checks ) ):
			reskeys.append( "{0}:{1}".format( s, checks[k] ) )
			resvals.append( checks[i] )

class TestReg:
	'''Test registry'''

	def __init__( self, rc, servName = None, host = None, port = None, acc = None, datafile = None,
				loglevel = None, logtopics = None ):
		self.rc = rc
		self.servName = servName
		self.host = host
		self.port = port
		self.acc = acc
		self.datafile = datafile
		self.loglevel = loglevel
		self.logtopics = logtopics

	def create( self ):
		global log
		log.info( "Creating registry %s" % self.servName )
		try:
			args = [rc, "--start"]
			if self.servName:
				args.append( sn )
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
			if self.loglevel:
				args.append( "--log-level" )
				args.append( self.loglevel )
			if self.logtopics:
				args.append( "--log-topics" )
				args.append( self.logtopics )

			sp.Popen( args )
			time.sleep( 2 )
		except sp.CalledProcessError as e:
			print( rc, "--start", "returned non-zero:", e.output )
			raise regd.ISException( regd.operationFailed )

	def sendCmd( self, *args_ ):
		args = [rc] + list( args_ )
		if self.servName:
			args.append( sn )
			args.append( self.servName )
		if self.host:
			args.append( "--host" )
			args.append( self.host )
		if self.port:
			args.append( "--port" )
			args.append( self.port )
		if self.loglevel:
			args.append( "--log-level" )
			args.append( self.loglevel )
		if self.logtopics:
			args.append( "--log-topics" )
			args.append( self.logtopics )

		return sp.check_output( args )

	def do_token_cmd( self, cmd, tokens, fb=None ):
		global log
		log.info( "Performing %s on name: %s ; host: %s:%s" % ( cmd, self.servName, self.host,
															self.port ) )

		for tok, cur in tokens:
			try:
				res = self.sendCmd( cmd, tok )
				res = res[:-1].decode( 'utf-8' )
				if res[0] != '1':
					print( cmd, "\nfailed:", res, "\n", cur )
					return False
			except sp.CalledProcessError as e:
				print( rc, cmd, "\nreturned non-zero:", e.output, "\n", cur )
				raise regd.ISException( regd.operationFailed )
			
			if fb: fb()

		log.info( "\n%s tokens were processed on name: %s ; host: %s:%s" % ( len( tokens ),
													self.servName, self.host, self.port ) )
		return True


	def compare( self, getCmd, checks, fb=None ):
		global log
		log.info( "Comparing registry %s" % self.servName )
		'''Compares the contents of the registry with the 'tokens' list.'''

		for key, val, cur in checks:
			try:
				res = self.sendCmd( getCmd, key )
				res = res[:-1].decode( 'utf-8' )

				if res[0] != '1':
					print( getCmd, "failed:", res, "\n", cur )
					return False

				if res[1:] != val:
					print( "Value and check don't match:\n  {0}\n  {1}\n{2}".format( res[1:],
															val, cur ) )
					return False

			except sp.CalledProcessError as e:
				print( rc, getCmd, "returned non-zero:", e.output )
				raise regd.ISException( regd.operationFailed )
			
			if fb: fb()


		log.info( "%s tokens were checked in registry '%s'" % ( len( checks ),
													self.servName if self.servName else "regd" ) )
		return True

	def checkToken( self, s, n, v ):
		if s[-1] == '\\': s += ' '
		if n[-1] == '\\': n += ' '
		tok = "{0}:{1}={2}".format( s.replace( ":", "\:" ), n.replace( "=", "\=" ), v )
		cmd = clp( regd.ADD_TOKEN )
		try:
			res = self.sendCmd( cmd, tok )
		except sp.CalledProcessError as e:
			print( rc, cmd, "returned non-zero:", e.output )
			return False

		if res != b'1\n':
			print( cmd, "failed:", res )
			return False

		cmd = clp( regd.GET_TOKEN )
		key = "{0}:{1}".format( s.replace( ":", "\:" ), n )
		try:
			res = self.sendCmd( cmd, key )
			res = res[:-1].decode( 'utf-8' )
		except sp.CalledProcessError as e:
			print( rc, cmd, "returned non-zero:", e.output )
			return False

		if res[0] != '1':
			print( cmd, "failed:", res )
			return False

		if res[1:] != v:
			print( "Value and check don't match:\n  {0}\n  {1}".format( res[1:], v ) )
			return False

		cmd = clp( regd.REMOVE_TOKEN )
		try:
			res = self.sendCmd( cmd, key )
			res = res[:-1].decode( 'utf-8' )
		except sp.CalledProcessError as e:
			print( rc, cmd, "returned non-zero:", e.output )
			return False

		if res[0] != '1':
			print( cmd, "failed:", res )
			return False

		return True

def start_servers( parmaps ):
	tregs = []
	for m in parmaps:
		treg = TestReg( rc, **m )
		try:
			treg.sendCmd( "--stop", "--no-verbose" )
		except:
			pass
		time.sleep( 2 )
		log.info( "Creating a %s with %s access..." %
				( 
				"IP-based server on {0}:{1} ".format( m['host'], m['port'] )
					if m['host'] else
				"file socket server with '{0}' name".format( m.get( "servName", "default" ) ),
				m.get( "acc", "private" )
				) )
		try:
			treg.create()
			tregs.append( treg )
		except:
			for treg in tregs:
				try:
					treg.sendCmd( "--stop", "--no-verbose" )
				except:
					pass
			raise
	time.sleep( 2 )
	return tregs

sids = None
nsids = None
startKeywords = ["servName", "host", "port", "datafile", "acc", "loglevel", "logtopics"]

def datafile_setup( sids ):
	tmpdir = os.getenv( "TMPDIR", "/tmp" )
	tstdatafile = tmpdir + "/regd_tst_{0}.data"
	dataf = []
	tf = TokenStringFeeder(toksections, toknames, tokvalues, len(toksections) ** 2)

	try:
		for i in sids:
			df = tstdatafile.format( i )
			fp = open( df, "w" )
			for tok in tf:
				fp.write(tok[0]+"\n")
			fp.close()
			dataf.append( df )
	except OSError as e:
		print( "ATTENTION: Could not create a temporary test data file at:", tmpdir, str( e ) )
		print( "\n\nPerforming test with persistent tokens not enabled." )
		dataf = ["None"] * len(sids)
		
	return dataf
		
def filesocket_setup( loglevel, logtopics ):
	global sids
	sids = [None, "public-read", "public"]
	dataf = datafile_setup(sids)

	params = []
	for i in range( 0, len( sids ) ):
		params.append( [sids[i], None, None, dataf[i], sids[i], loglevel, logtopics] )

	parmaps = []
	for i in range( 0, len( params ) ):
		parmaps.append( dict( zip( startKeywords, params[i] ) ) )

	return start_servers( parmaps )

def filesocket_finish():
	for i in sids:
		try:
			if i:
				sp.call( [rc, sn, i, "--stop", "--no-verbose"] )
			else:
				sp.call( [rc, "--stop", "--no-verbose"] )
		except:
			pass

def network_setup(nsids_, loglevel, logtopics):
	global nsids
	nsids = nsids_[:]
	dataf = datafile_setup([x+"-"+y for x,y in nsids])
	params = []
	for i in range(0, len(nsids)):
		params.append( [None, nsids[i][0], nsids[i][1], dataf[i], None, loglevel, logtopics] )

	parmaps = []
	for i in range( 0, len( params ) ):
		parmaps.append( dict( zip( startKeywords, params[i] ) ) )

	return start_servers( parmaps )

def network_finish():
	for host,port in nsids:
		try:
			sp.call( [rc, "--host", host, "--port", port, "--stop", "--no-verbose"] )
		except:
			pass
		
def multiuser_setup(username, loglevel, logtopics):
	'''Client side of multiuser test'''
	global sids
	sids = ["@", "@public-read", "@public"]

	params = []
	for i in range( 0, len( sids ) ):
		params.append( [username+sids[i], None, None, None, None, loglevel, logtopics] )

	parmaps = []
	for i in range( 0, len( params ) ):
		parmaps.append( dict( zip( startKeywords, params[i] ) ) )
	
	tregs=[]
	for m in parmaps:
		treg = TestReg( rc, **m )
		tregs.append(treg)
		
	return tregs
		
def multiuser_finish():
	pass
		
def begin_multiuser_test():
	'''Server side of multiuser test.'''
	
	print( "MULTIUSER test setup began..." )
	cp = ConfigParser()
	if tstconf:
		cp.read( tstconf )
	if not cp.has_section( "general" ):
		cp.add_section( "general" )
	loglevel = cp["general"].get( "loglevel", "1" )
	if loglevel not in "123":
		loglevel = "1"

	try:
		tregs = filesocket_setup( loglevel, None )
		tf = TokenStringFeeder( toksections, toknames, tokvalues )
		cf = ChecksFeeder( toksections, toknames, tokvalues )
		for treg in tregs:
			log.info( "Adding tokens to the server..." )
			treg.do_token_cmd( "--add", tf )
			if treg.datafile != "None":
				treg.do_token_cmd( "--add-pers", tf )
			log.info( "Checking tokens on the server..." )
			treg.compare( "--get", cf )
			if treg.datafile != "None":
				treg.compare( "--get-pers", cf )
	except:
		print( "Some errors occured. The multi user test has NOT been set up." )
		return

	print( "Finished multiuser test setup." )
	print( "'regd --test-start' can now be run on other user accounts, configured for",
		"multiuser test with this account.\nAfter the tests are done, the",
		"'regd --test-multiuser-end' should be called on this account" )

def end_multiuser_test():
	filesocket_finish()
	print( "MULTIUSER test finished." )

def do_basic_test():
	print( "BASIC test started." )
	try:
		tregs = filesocket_setup( "INFO", None )
	except:
		print( "Error: some errors occured during the test setup. The test has not been completed." )
		return

	tf = TokenStringFeeder( testtokens )
	cf = ChecksFeeder( testtokens )
	tk = KeysFeeder( testtokens )

	for treg in tregs:
		treg.do_token_cmd( "--add", tf )
		treg.compare( "--get", cf )
		tf.reset()
		cf.reset()

	for treg in tregs:
		treg.do_token_cmd( "--remove", tk )
		tk.reset()

	filesocket_finish()


def basic_test_debug():
	global tok_checks, toksections, toknames, tokvalues

	regd.setLog( "WARNING", "tokens" )
	# regd.setLog( "WARNING" )

	if 1:
		tok = "\\\:\:= \\\: \\==:\\:=\\::= \\: \\=="
		sec, nam, val = regd.parse_token( tok )
		print( sec, nam, val )
		return


	treg = TestReg( rc, servName = "tst", loglevel = "INFO", logtopics = "tokens" )
	# treg = TestReg( rc, servName="tst", loglevel="INFO" )
	try:
		treg.sendCmd( "--stop" )
	except:
		pass
	time.sleep( 2 )
	treg.create()
	time.sleep( 3 )

	if 0:
		tf = TokenFeeder( tokvalues )
		treg.checkToken( *( tf.getToken( 0, 2, 0 ) ) )
		# treg.checkToken( "\\", "=", "\\")
		return
		for ( s, n, v ), cur in tf:
			if not treg.checkToken( s, n, v ):
				print( "Check failed for token", cur )
				break
			else:
				print( cur )

		return

	# tokens = []
	# keychecks = []
	# valchecks = []

	# toksections=["a\:", "a\\\:"]
	# toknames=["a:", "a\\:"]
	# tokvalues=["a:", "a\\:"]
	# tok_checks = []
	# tok_checks = ["a:", "a\\:"]
	# compose_tokens( tokvalues, tokens )
	# compose_checks(tokvalues, keychecks, valchecks)
	# arr = ["aaa", "bbb"]
	# compose_tokens(arr, arr, arr, tokens)
	# compose_checks(arr, keychecks, valchecks)
	tf = TokenStringFeeder( tokvalues, num = 5 )
	cf = ChecksFeeder( tokvalues, num = 5 )
	tk = KeysFeeder( tokvalues, num = 5 )
	treg.do_token_cmd( "--add", tf )
	treg.compare( "--get", cf )
	treg.do_token_cmd( "--remove", tk )

def test_configure():
	if not tstconf:
		print( "Error: the directory for storing the test configuration file",
			"is not available. Exiting." )
		return

	print( "Please select the test type to perform:\n" )
	print( "1. BASIC: testing regd as a file socket based server.\n" )
	print( "2. NETWORK: testing regd as an IP-based server.\n" )
	print( "3. MULTIUSER: testing accessing a regd server running on another user account.\n" )
	s = input( "Type the test number (or 'q' for exit) and press 'Enter':\n> " )
	while s not in ['1', '2', '3', 'q']:
		s = input( "Please type a number from 1 to 3 or 'q' and press 'Enter':\n> " )
	if s in 'Qq':
		print( "Exiting." )
		return


	cp = ConfigParser()
	cp.read( tstconf )
	if not cp.has_section( "general" ):
		cp.add_section( "general" )
	cp.set( "general", "test_type", s )

	def conf2():
		rehost = "[a-zA-Z0-9\.-]+"
		while True:
			host = input( ( "\n\n\nPlease enter the host name to which the regd server should be bound"
						" ('.' for quit):\n> " ) )
			if host == '.':
				return '.'
			if not re.match( rehost, host ):
				print( "This name contains invalid characters. Only numbers, letters, dots and",
					"hyphens are allowed." )
				continue
			if len( host ) > 255:
				print( "This name is too long." )
				continue

			while True:
				port = input( ( "\n\n\nPlease enter the port number on which the regd server should be listening"
						"\n('.' for quit, 'Enter' for default port number 48473):\n> " ) )
				if port == '.':
					return '.'
				if not port:
					port = '48473'
				elif not re.match( "[0-9]+", port ):
					print( "Port number must only contain digits." )
					continue
				elif int( port ) > 65536:
					print( "The number must be no greater than 65536." )
					continue
				break

			ans = input( ( "\n\n\nregd will be tried to start on host: {0} port: {1}. Accept these settings?"
				"\n([Y]es, [n]o, [q]uit)> " ).format( host, port ) )
			if ans in "Yy":
				return ( host, port )
			if ans in "Qq":
				return '.'

	def conf3():
		print( "\n\n\nIn the multiuser test the regd server runs on another user account",
					"and is contacted from this account." )
		while True:
			name = input( ( "\n\n\nPlease enter the username of the user"
					" account where the test regd server will run ('.' for quit):\n> " ) )
			if name == '.':
				return '.'

			try:
				pwd.getpwnam( name ).pw_uid
			except KeyError:
				print( "No such user account is found on this system." )
				continue

			return name

	def getloglevel():
		print( "\n\n\nPlease select the level of verbosity of information output during testing: \n" )
		print( "1. NORMAL (recommended)" )
		print( "2. VERBOSE (may help if some tests went wrong)" )
		print( "3. DEBUG (for developers)\n" )
		while True:
			loglevel = input( "Number (1, 2 or 3) or 'q' for quit: " )
			if loglevel in "123qQ":
				break
		return loglevel

	def write_conf():
		nonlocal cp
		try:
			fp = open( tstconf, "w" )
			cp.write( fp, True )
		except OSError as e:
			print( "Error: could not write the test configuration file: ", e.strerror )
			return False

		return True

	if s == '1':
		prompt = "The test has been configured. You can now run 'regd --test-start' to start it."
	elif s == '2':
		ret = conf2()
		if ret == '.':
			return
		cp.set( "general", "host", ret[0] )
		cp.set( "general", "port", ret[1] )
		prompt = "The test has been configured. You can now run 'regd --test-start' to start it."
	elif s == '3':
		ret = conf2()
		if ret == '.':
			return
		cp.set( "general", "host", ret[0] )
		cp.set( "general", "port", ret[1] )
		ret = conf3()
		if ret == '.':
			return
		cp.set( "general", "multiuser", ret )

		prompt = ( "The test has been configured.  Now the 'regd --test-multiuser-begin' command",
			"must be called from the '{0}' user account. After that, the 'regd --test-start'",
			"command must be called from this account. After the tests are done,"
			"'regd --test-multiuser-end' should be called on '{0}' user account." ).format( ret )

	ret = getloglevel()
	if ret == 'q':
		return
	cp.set( "general", "loglevel", ret )

	if not write_conf():
		prompt = "The test configuration failed."
	input( "\n\n\n" + prompt + "\n\nPress 'Enter' to quit." )

def main( *kwargs ):
	global log, logtok, tstconf
	parser = argparse.ArgumentParser( 
		description = 'test_help : Testing helper.'
	)

	parser.add_argument( '--log-level', default = "2", help = 'Logging level: 1, 2 or 3' )
	group = parser.add_mutually_exclusive_group()

	group.add_argument( '--test-multiuser-begin', action = 'store_true', help = 'Initialize regd for multi-user test.' )
	group.add_argument( '--test-multiuser-end', action = 'store_true', help = 'Ends multi-user test.' )
	group.add_argument( '--test-configure', action = 'store_true', help = 'Configure the regd test.' )
	group.add_argument( '--test-basic', action = 'store_true', help = 'Perform the basic test.' )

	args = parser.parse_args( *kwargs )

	# Config file
	tstconf = regd.get_conf_dir() + "/test.conf"
	if not os.path.exists( tstconf ):
		if os.path.exists( regd.get_conf_dir() ):
			with open( tstconf, "w" ) as f:
				f.write( "" )

	# Setting up logging

	log = logging.getLogger( "tests" )
	# log_level = getattr( logging, args.log_level )
	log_level = args.log_level
	if log_level == "1":
		log_level = logging.CRITICAL
	elif log_level == "2":
		log_level = logging.INFO
	elif log_level == "3":
		log_level = logging.DEBUG

	setLog( log_level )

	if args.test_basic:
		try:
			do_basic_test()
		except:
			print( "Test failed" )
	elif args.test_configure:
		test_configure()

	else:
		# basic_test_debug()
		do_basic_test()




if __name__ == "__main__":
	sys.exit( main( sys.argv[1:] ) )
