'''
/********************************************************************
*	Module:		regd.rgfs
*
*	Created:	Jul 28, 2015
*
*	Abstract:	Regd FUSE server.	
*
*	Author:		Albert Berger [ alberger@gmail.com ].
*		
*********************************************************************/
'''
__lastedited__="2015-08-08 04:42:07"

import sys, argparse, logging
from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import argv, exit
from time import time
from regd.comm import RegdComm
import regd.comm as comm, regd.defs as defs

from fusepy.fuse import FUSE, FuseOSError, Operations, LoggingMixIn
import regd.util as util 


class RegdFS(LoggingMixIn, Operations):
	'Example memory filesystem. Supports only one level of files.'

	def __init__( self, servaddr, mountpoint ):
		self.servaddr = servaddr
		self.mountpoint = mountpoint
		self.rcom = RegdComm( servaddr )
		self.fd = 0
		
	def rcmd( self, path, cmd, data=None):
		'''The first component of the path is the server address:
		/user@server/ , /user@/ , /@/ - file socket servers;
		/host:NNNN/ - IP based servers
		'''
		addr,_,_ = path[1:].partition("/")
		return comm.regdcmd( { "cmd": cmd, "params": data }, addr)		

	def chmod(self, path, mode):
		self.rcmd(path, "chmod", str(mode))
		#self.files[path]['st_mode'] &= 0o770000
		#self.files[path]['st_mode'] |= mode
		return 0

	def chown(self, path, uid, gid):
		self.rcmd(path, "chown", "{0}:{1}".format(uid, gid))
		#self.files[path]['st_uid'] = uid
		#self.files[path]['st_gid'] = gid

	def create(self, path, mode):
		'''
		self.files[path] = dict(st_mode=(S_IFREG | mode), st_nlink=1,
								st_size=0, st_ctime=time(), st_mtime=time(),
								st_atime=time())
		'''
		print( "create: path: ", path, "mode: ", mode )
		self.rcom.addToken(path, None)

		self.fd += 1
		return self.fd

	def getattr(self, path, fh=None):
		print("getattr: path: ", path)
		res, ret = self.rcom.sendCmd( { "cmd": defs.GETATTR, "params": [path] } )
		print(res, ret)
		if not res:
			raise FuseOSError(ENOENT)
		return ret

	def getxattr(self, path, name, position=0):
		print( "getxattr; path: ", path, "; name: ", name )
		attrs = {} # self.files[path].get('attrs', {})

		try:
			return attrs[name]
		except KeyError:
			return b''	   # Should return ENOATTR

	def listxattr(self, path):
		attrs = {} #self.files[path].get('attrs', {})
		return attrs.keys()

	def mkdir(self, path, mode):
		'''
		self.files[path] = dict(st_mode=(S_IFDIR | mode), st_nlink=2,
								st_size=0, st_ctime=time(), st_mtime=time(),
								st_atime=time())

		self.files['/']['st_nlink'] += 1
		'''
		self.rcom.createSection(path, None)

	def open(self, path, flags):
		print( "open: path: ", path, "; flags: ", flags )
		self.fd += 1
		return self.fd

	def read(self, path, size, offset, fh):
		print("read: path: {0}; size: {1}; offset: {2}; fh: {3}".format( path, size, offset, fh))

		res, ret = self.rcom.sendCmd( { "cmd": defs.GET_TOKEN, "params": [path] } )
		if res:
			if type( ret ) is str:
				ret = ret.encode('utf-8')
		print( ret )
		return bytes(ret) if res else bytes(b'')
		#return self.data[path][offset:offset + size]

	def readdir(self, path, fh):
		print( "readdir: ", path )
		lres = [] #['.', '..'] #+ [x[1:] for x in self.files if x != '/']
		if not self.rcom.listTokens(lres, path, defs.NOVALUES):
			print("Error: failed to list directory {0}:\n{1}".format(path, lres[0]))
			return ""
		ret = ['.', '..']
		for tok in lres:
			if not tok:
				continue
			if tok[0] == '[' and tok[-1]==']':
				ret.append( tok[1:-1] )
			else:
				ret.append( tok )	

		print( ret )
		return ret

	def readlink(self, path):
		#return self.data[path]
		return ''

	def removexattr(self, path, name):
		attrs = {}#self.files[path].get('attrs', {})

		try:
			del attrs[name]
		except KeyError:
			pass		# Should return ENOATTR

	def rename(self, old, new):
		#self.files[new] = self.files.pop(old)
		self.rcom.rename(old, new)

	def rmdir(self, path):
		#self.files.pop(path)
		#self.files['/']['st_nlink'] -= 1
		self.comm.sendCmd( { "cmd": defs.REMOVE_SECTION, "params": [path] } )

	def setxattr(self, path, name, value, options, position=0):
		# Ignore options
		attrs = {}#self.files[path].setdefault('attrs', {})
		attrs[name] = value

	def statfs(self, path):
		print("statfs; path: ", path)
		return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

	def symlink(self, target, source):
		'''
		self.files[target] = dict(st_mode=(S_IFLNK | 0o777), st_nlink=1,
								  st_size=len(source))

		self.data[target] = source
		'''
		pass

	def truncate(self, path, length, fh=None):
		#self.data[path] = self.data[path][:length]
		#self.files[path]['st_size'] = length
		pass

	def unlink(self, path):
		self.rcom.sendCmd( { "cmd": defs.REMOVE_TOKEN, "params": [path] } )
		#self.files.pop(path)

	def utimens(self, path, times=None):
		now = time()
		atime, mtime = times if times else (now, now)
		#self.files[path]['st_atime'] = atime
		#self.files[path]['st_mtime'] = mtime

	def write(self, path, data, offset, fh):
		print( "write: path: ", path, "; data: ", data, "; offset: ", offset )
		#self.data[path] = self.data[path][:offset] + data
		#self.files[path]['st_size'] = len(self.data[path])
		self.rcom.addToken(path, None, defs.FORCE, **{defs.BINARY: [data]})
		#regdcmd("add", ["{0}={1}".format(path[1:], data)])
		#sp.call(["regd","add", "{0}={1}".format(path, data)])
		return len(data)


class RegdFuseApp(object):
	def __init__(self):
		pass
		
	def main(self, *args):
		parser = argparse.ArgumentParser( 
			description = 'Regd FUSE server.'
		)
		parser.add_argument( 'servaddr', help = "Server address (server name or server's IP address).")
		parser.add_argument( 'mountpoint', help = "Mount point.")
		# Log level for stdout
		parser.add_argument( '--log-level', default = 'WARNING', help = 'DEBUG, INFO, WARNING, ERROR, CRITICAL' )
		
		args = parser.parse_args()
		loglevel = args.log_level
		util.setLog(loglevel, None)		

		logging.getLogger().setLevel(logging.DEBUG)
		fuse = FUSE( RegdFS( args.servaddr, args.mountpoint ), args.mountpoint, foreground=True)
			
if __name__ == "__main__":
	RegdFuseApp().main(sys.argv)