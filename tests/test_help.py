#!/usr/bin/env python3
'''********************************************************************
*	Package:       tests
*	
*	Module:        test_help.py
*
*	Created:	   2015-Jun-18 13:20:25 PM
*
*	Abstract:	   Function for sending commands to regd. 
*
*	Copyright:	   Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__ = "2015-06-19 03:36:11"


import sys, os.path, socket, argparse, pwd
import subprocess as sp
import regd

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
		sock.settimeout(3)
	
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
			if cmd.startswith("--"):
				cmd = cmd[2:]
			cmd = cmd.replace('-', '_')
			if not cmd.startswith( regd.CMDMARKER ):
				cmd = regd.CMDMARKER + cmd
				
			data = cmd + ' ' + data			
		
		bPacket = bytearray( data + regd.EODMARKER, encoding='utf-8' )
		
		sock.sendall( bPacket )
		
		data = bytearray()
		eodsize = len( regd.EODMARKER )
		# Format of the response packet: <4b: packet length><4b: response code>[data]
		while True:
			data.extend( sock.recv( 4096 ) )
			datalen = len( data )
			if datalen >= eodsize and data[-eodsize:].decode('utf-8') == regd.EODMARKER:
				break
			
		data = data[:-eodsize].decode('utf-8')
		
		#res = struct.unpack_from("L", data, offset=0)[0]
		
		sock.shutdown(socket.SHUT_RDWR)
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

sn = "--server-name"
add = "--add"
tokens = ["aaa=bbb",
"secname: aaa=bbb",
"sec\\na\"me\:\:\\\: with =misc = \'()*$`~!==|\\:aaa=bbb",
"secname:tok\\\=name:with\=misc\"\'\=()*$`~!\=\= |:\\= bbb",
"sec\\name\:\:\\\:with=misc=()*$`~!==|\\:tok\\\=name:with\=misc\=()*$`~!\=\=|:\\==:--=\\\'\" ;",
"section1:name1=value1",
"section1:name2=value2",
"section1:name3=value3",
"section2:name4=value4",
"section2:name5=value5",
"section2:name6=value6"
]

class tstReg:
	def fill( self, addCmd, name, rc="../regd/regd.py" ):
		for i in range(0,10):
			try:
				sp.Popen([rc, sn, name, addCmd, tokens[i]])
			except sp.CalledProcessError as e:
				print( rc, addCmd, "returned non-zero:", e.output )

def start_multiuser_test():
	dir = os.path.dirname(__file__)
	username = pwd.getpwuid(os.getuid())[0]
	with open( dir + "test.conf", "w" ) as f:
		f.write( username )
	
		

def main():
	
	parser = argparse.ArgumentParser( 
		description = 'test_help : Testing helper.'
	)
	
	group = parser.add_mutually_exclusive_group()
	
	group.add_argument( '--start-multiuser-test', nargs = 0, action = 'store_true', help = 'Initialize regd for multi-user test.' )
	group.add_argument( '--stop-multiuser-test', nargs = 0, action = 'store_true', help = 'Ends multi-user test.' )

if __name__ == "__main__":
	sys.exit( main() )