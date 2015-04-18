#!/usr/bin/env python
'''********************************************************************
*	Module:			safestor
*	
*	File name:		safestor.py
*
*	Created:		2015-Apr-05 06:20:25 PM
*
*	Abstract:		Local server which stores private data in encrypted 
*					form and provides it on requests. 
*
*	Copyright:		Albert Berger, 2015.
*
*********************************************************************'''

__lastedited__="2015-04-18 11:45:34"

VERSION = (0, 1)
__version__ = '.'.join(map(str, VERSION[0:2]))
__description__ = 'Secure text storage'
__author__ = 'Albert Berger'
__author_email__ = 'alberger@gmail.com'
__homepage__ = 'https://github.com/nbdsp/safestor'
__license__ = 'BSD'

import sys, os, socket, signal, subprocess

THISFILE = os.path.basename( __file__ ) 
USAGE = ( "Usage: \n"
		"{0}  <item_name> - outputs the <item_name> data."   
		"{0} --start - starts server\n"
		"{0} --stops - stops server.\n\n").format( THISFILE )
EODMARKER = "%^&"

sockdir = '/var/run/user/{0}'.format( os.getuid() )
server_address = '{0}/.{1}.sock'.format( sockdir, "safestor" )
CONFFILE = os.path.expanduser('~') + "/.config/safestor/safestor.conf"
ENCFILE = os.path.expanduser('~') + "/.sec/safestor.gpg"
items = {}

def signal_handler(signal, frame):
	os.unlink(server_address)
	sys.exit(1)

def contactServer( item ):
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.settimeout(3)

	try:
		sock.connect( server_address )
	except OSError as er:
		sys.stderr.write( "safestor connect: Socket error {0}: {1}\nServer address: {2}".format( 
												er.errno, er.strerror, server_address ) )
		sys.exit(-1)

	try:
		# Creating packet: <data><endOfDataMarker>
		bPacket = bytearray( item + EODMARKER, encoding='utf-8' )
		
		sock.sendall( bPacket )
		
		eodsize = len( EODMARKER )
		while True:
			data = sock.recv(4096)
			datalen = len( data )
			if datalen >= eodsize and data[-eodsize:].decode('utf-8') == EODMARKER:
				break
		
		sock.shutdown(socket.SHUT_RDWR)
		sock.close()
		
		return data[:-eodsize].decode('utf-8')
	except OSError as er:
		sys.stderr.write( 
			"safestor: contactServer: Socket error {0}: {1}\nServer address: {2}\n".format( 
												er.errno, er.strerror, server_address ) )
		sys.exit(-1)


def startServer():
	try:
		os.unlink( server_address )
	except OSError:
		if os.path.exists( server_address ):
			raise
	
	eodsize = len( EODMARKER )
	sock = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
	sock.bind( server_address )

	sock.listen(1)
	
	while True:
		connection, client_address = sock.accept()
		connection.settimeout(3)
		try:
			while True:
				data = connection.recv(4096)
				datalen = len( data )
				if datalen >= eodsize and data[-eodsize:].decode('utf-8') == EODMARKER:
					break
			
			data = data[:-eodsize].decode('utf-8')
		
			resp = ""
			if data in items:
				resp = items[data]
			elif data == "--stop":
				resp = "1"
		
			resp += EODMARKER

			try:
				connection.sendall( bytearray( resp, encoding='utf-8' ) )
			except OSError as er:
				sys.stderr.write( "Safestor server: Socket error {0}: {1}\nClient address: {2}\n".format( 
								er.errno, er.strerror, client_address ))
				
			if data == "--stop":
				os.unlink(server_address)
				return 0
				
		finally:
			connection.shutdown( socket.SHUT_RDWR )
			connection.close()		

def main():
	'''
	Query format: safestor.py <item>
	--start and --stop items start and stop server.
	'''
	global ENCFILE
	
	if len(sys.argv) < 2:
		item = ""
	else:
		item = sys.argv[1]
				
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)
	signal.signal(signal.SIGHUP, signal_handler)
	signal.signal(signal.SIGABRT, signal_handler)
	
	if os.path.exists( CONFFILE ):
		with open( CONFFILE ) as f:
			for s in f:
				key,_,val = s.partition( "=" )
				if key.strip() == 'encfile':
					ENCFILE = val.strip()
	
	if item == '--start': 
		if not os.path.exists( server_address ):
			if not os.path.exists( ENCFILE ):
				sys.stderr.write( "safestor: Cannot file encrypted data file. Exiting.\n")
				return -1

			ftxt = subprocess.check_output("gpg --textmode -d {0}".format( ENCFILE ), shell = True,
									stderr=subprocess.STDOUT )
			ftxt = ftxt.decode('utf-8')
			ltxt = ftxt.split("\n")
		
			for s in ltxt:
				key,_,val = s.strip().partition("=")
				items[key] = val
			return startServer()
		else:
			sys.stderr.write( "safestor is already running.\n")
			return 1
		
	elif item == '--stop':
		if not os.path.exists( server_address ):
			return 1

		if contactServer(item) != "1":
			sys.stderr.write( "safestor: Cannot contact server.\n" )
			return -1

		return 0
		
	else:
		if os.path.exists( server_address ):
			# Server is running. Querying it.
			ret = contactServer(item)
		else:
			# Server is not running. Doing one-time file read.
			ftxt = subprocess.check_output("gpg --textmode -d {0}".format( ENCFILE ), shell = True,
									stderr=subprocess.STDOUT )
			ftxt = ftxt.decode('utf-8')
			ltxt = ftxt.split("\n")
		
			for s in ltxt:
				key,_,val = s.strip().partition("=")
				if key == item:
					ret = val
				
		if len( ret ) == 0:
			print ("")
			return 1
		
		print(ret)
		
	return 0
	

if __name__ == "__main__":
	sys.exit( main() )