'''
/********************************************************************
*	Module:			regd.stor
*
*	Created:		Jul 5, 2015
*
*	Abstract:		Storage.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*********************************************************************/
'''
__lastedited__="2015-11-26 12:07:30"

import sys, re, subprocess, tempfile, os, time
from enum import Enum
from regd.util import log, logtok, ISException, unknownDataFormat, operationFailed, \
	objectNotExists, valueAlreadyExists, valueNotExists, unrecognizedParameter, programError
import regd.defs as defs
from regd.tok import parse_token, stripOne
from collections import deque, OrderedDict

from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG

SECTIONPATT="^\[(.*)\]$"
SECTIONNAMEPATT="^(.*?)(?<!\\\):(.*)"
TOKENPATT="^(.*?)(?<!\\\)=(.*)"
MULTILINETOKENPATT="^[ \t](.*)$"
NUMBERPATT="\-?([0-9]*\.)?[0-9]+"

reNumber = re.compile( NUMBERPATT )

PERSNAME = "sav"
SESNAME = "ses"
PERSPATH = "/" + PERSNAME
SESPATH = "/" + SESNAME

rootdirs = [SESPATH, PERSPATH]

class EnumMode(Enum):
	both		= 1
	tokens		= 2
	sections 	= 3
	all 		= 4
	tokensAll	= 5
	sectionsAll	= 6
	
class st_struct:
	'''stat struct'''
	def __init__(self, mode=None, uid=None, gid=None, ctime=None, mtime=None, atime=None,
				nlink=None):
		nowtm = time.time() 
		self.st_mode = mode if mode else 0o644 
		self.st_uid = uid if uid else os.getuid()
		self.st_gid = gid if gid else os.getgid()
		self.st_ctime = ctime if ctime else nowtm 
		self.st_mtime = mtime if mtime else nowtm 
		self.st_atime = atime if atime else nowtm 
		self.st_nlink = nlink if nlink else 1
	
class SItem:
	'''Storage item'''
	def __init__(self, itype, mode=None, uid=None, gid=None, ctime=None, mtime=None, atime=None,
				nlink=None):
		self.itype = itype
		self.st = st_struct(mode, uid, gid, ctime, mtime, atime, nlink)
		return super(SItem, self).__init__( )
	
	def getAttr(self, attrName = None):
		if not attrName:
			st_mode = (self.itype | self.st.st_mode)
			ret = {'st_mode':st_mode, 'st_uid':self.st.st_uid, 'st_gid':self.st.st_gid,
				'st_dev':0, 'st_rdev':0, 'st_ino':0, 'st_size':self.getsize(), 
				'st_blksize':2048, 'st_blocks':(int(self.getsize()/512))+1, 
				'st_ctime':int(self.st.st_ctime), 
				'st_atime':int(self.st.st_atime), 'st_mtime':int(self.st.st_mtime) }
			return ret
		
	def setAttr(self, **kwargs):
		for k, v in kwargs.items():
			if k == 'st_mode':
				self.st_mode = v
				
	def getsize(self):
		pass
				
		
class SVal(SItem):
	'''Storage value container.'''
	def __init__(self, val=None, mode=None, uid=None, gid=None, ctime=None, mtime=None, atime=None,
				nlink=None):
		self.val = val
		return super(SVal, self).__init__( S_IFREG, mode, uid, gid, ctime, mtime, atime, nlink )
	
	def __str__(self):
		if type(self.val) is bytes or type(self.val) is bytearray:
			return self.val.decode( 'utf-8' )
		elif type( self.val ) is str:
			return self.val
		else:
			return str ( self.val )
		
	def getsize(self):
		return len( self.val ) if self.val else 0

class Stor(SItem, dict):
	def __init__(self, name='', mode=None, uid=None, gid=None, ctime=None, mtime=None, atime=None,
				nlink=None):
		self.name = name
		self.path = ''
		self.enumMode = None
		return super(Stor, self).__init__( S_IFDIR, mode, uid, gid, ctime, mtime, atime, nlink )
		
	def __getitem__( self, key ):
		item = super(Stor, self).__getitem__( key )
		if isinstance( item, baseSectType ):
			return item
		elif isinstance(item, baseValType):
			return item.val
		else:
			raise ISException( programError, "Storage item type is: {0}".format(str(type(item))))
	
	def get(self, *args, **kwargs):
		return dict.get(self, *args, **kwargs)
	
	def __setitem__( self, key, val ):
		if self.name and not key:
			raise ISException(unrecognizedParameter, "section name is empty")
		if key:
			if "/" in key:
				raise ISException(unrecognizedParameter, "section name contains '/'")
			if key == '.':
				raise ISException(unrecognizedParameter, key, "not valid section name")
		if type(val) == type(self):
			if self.path:
				val.setPath( self.path + "/" + self.name )
			else:
				if self.name:
					val.setPath( "/" + self.name )
				else:
					val.setPath( '' )
			val.setName( key )
		else:
			if type( val ) != SVal:
				val = SVal( val, 0o644, self.st.st_uid, self.st.st_gid )
			
		return super(Stor, self).__setitem__( key, val )
	
	def __delitem__( self, key ):
		return super(Stor, self).__delitem__( key )
	
	def __contains__( self, key ):
		return super(Stor, self).__contains__( key )
	
	class StorIter:
		def __init__(self, stor, mode):
			self.mode = mode
			self.secdeq = deque()
			self.it = iter( stor )
			self.cd = stor # current dict
			self.tp = type( stor ) # section type  
			
		def __next__(self):
			while 1:
				try:
					item = next( self.it )
				except StopIteration:
					if len( self.secdeq ):
						self.cd = self.secdeq.popleft()
						self.it = iter( self.cd )
						continue
					else:
						raise 
					
				if isinstance( self.cd[item], self.tp ):
					if self.mode in (EnumMode.all, EnumMode.tokensAll, EnumMode.sectionsAll):
						self.secdeq.append( self.cd[item] )
					if self.mode in ( EnumMode.all, EnumMode.sections, EnumMode.sectionsAll ):
						return None, self.cd[item].pathName() 
				else:
					return item, self.cd[item]
			
			
	
	def __iter__(self, *args, **kwargs):
		if self.enumMode == None:
			return dict.__iter__(self, *args, **kwargs)
		em = self.enumMode
		self.enumMode = None
		it = Stor.StorIter(self, em)
		
		return it
	
	def getsize(self):
		return 0
	
	def enumerate(self, mode):
		self.enumMode = mode
		
	def setPath( self, path ):
		self.path = path
		for v in self.values():
			if self.path:
				v.setPath( self.path + "/" + self.name )
			else:
				if self.name:
					v.setPath( "/" + self.name )
				else:
					raise ISException(programError, "Storage item has no name.")
	
	def setName( self, name ):
		self.name = name
		
	def pathName(self):
		#if self.path:
		return self.path + "/" + self.name
		#else:
		#	return self.name
		
	def isPathValid( self, path ):
		if not path:
			return False
		
		if path[0] != '/':
			if self.name:
				path = self.pathName() + "/" + path
		else:
			# Absolute paths can only be added at the root section
			if self.name:
				return False			
		
		b = False
		if path[0] == '/':
			for d in rootdirs:
				if path.startswith( d ):
					b = True
					break
			if not b:
				return False
			
		if path.find('//') != -1:
			return False
		
		return True	
	
	def numItems(self, itemType=EnumMode.both):
		cnt = None
		if itemType == EnumMode.both:
			cnt = len( self )
		elif itemType in ( EnumMode.tokens, EnumMode.tokensAll ):
			cnt = 0
			for k in self.keys():
				if type( self[k] ) != type(self):
					cnt += 1
				elif itemType == EnumMode.tokensAll:
					cnt += self[k].numItems(EnumMode.tokensAll)
					
		elif itemType in ( EnumMode.sections, EnumMode.sectionsAll ):
			cnt = 0
			for k in self.keys():
				if type( self[k] ) == type(self):
					cnt += 1
					if itemType == EnumMode.sectionsAll:
						cnt += self[k].numItems(EnumMode.sectionsAll)
		elif itemType == EnumMode.all:
			cnt = self.numItems(EnumMode.tokensAll) + self.numItems(EnumMode.sectionsAll)
		else:
			raise ISException()
		return cnt
	
	def getSItemAttr( self, path, attrName=None ):
		item = self.getSItem( path )
		return item.getAttr( attrName )
	
	def setSItemAttr( self, path, **kwargs ):
		item = self.getSItem( path )
		return item.setAttr( kwargs )	
		
	def getSItem( self, path ):
		if type( path ) is str:
			if path[-1] == '/':
				return self.getSectionFromStr(path)
			else:
				return self.getToken( path )
		else:
			return self.getSection(path)
			
	def getSection( self, path ):
		if path:
			if path[0] not in self.keys() or not isinstance( self[path[0]], baseSectType ):
				raise ISException(objectNotExists, path[0], "Section doesn't exist")
			if len(path) > 1:
				return self[path[0]].getSection(path[1:])
			else:
				return self[path[0]]
		
		return self
	
		if not self.name == path:
			curname, _, path  = path.partition( '/' )
			if curname != self.name:
				raise ISException(objectNotExists, curname+'/'+path, "Section doesn't exist")
			sec, _, path = path.partition('/')
			if sec not in self.keys():
				raise ISException(objectNotExists, path, "Section doesn't exist")
			
			return self[sec].getSection( path )
		
		return self
	
	def getSectionFromStr(self, path):
		logtok.debug( "path: %s" % path)
		lpath, _, _ = parse_token( path, False, False)
		return self.getSection(lpath)
		
	def createSection(self, sec):
		if not self.isPathValid(sec):
			raise ISException(unrecognizedParameter, sec, "Section name is not valid.")
		curname, _, path = sec.partition('/')
		if not curname and self.name:
			raise ISException(unrecognizedParameter, sec, "Section name is not valid.")
		
		if curname not in self.keys():
			if self.name:
				self[curname] = getstor()
			else:
				raise ISException(unrecognizedParameter, sec, "Section doesn't exist.")
		
		if path:
			return self[curname].createSection(path)
		else:
			return self[curname]
		
	def addSection(self, sec):
		'''Adds a new section. 
		sec : string with the section path or the section SItem object.'''
		
		if isinstance( sec, baseSectType ):
			self[sec.name] = sec
		else:
			self.createSection( sec )	
		
	def addTokenToDest(self, dest, tok, addMode=defs.noOverwrite, binaryVal=None):
		path, _, _ = parse_token(dest, False, False)
		try:
			sec = self.getSection( path )
		except ISException as e:
			if e.code == objectNotExists:
				sec = self.createSection( dest )
			else:
				raise 
		sec.addToken( tok, addMode, binaryVal )
		
	def addToken( self, tok, addMode=defs.noOverwrite, binaryVal=None ):
		if not binaryVal:
			path, nam, val = parse_token(tok)
		else:
			path, nam, _ = parse_token( tok, True, False )
			val = binaryVal
		
		logtok.debug("[tok: {0}]:  path: {1} ; nam: {2} ; val: {3}".format( tok, path, nam, val))
		
		if not nam:
			raise ISException( unknownDataFormat, tok )
		try:
			sec = self.getSection( path )
		except ISException as e:
			if e.code == objectNotExists:
				sec = self.createSection( "/".join(path) )
			else:
				raise 
	
		sec.insertNamVal( nam, val, addMode )
		
	def insertNamVal(self, nam, val, addMode=defs.noOverwrite):
		if nam in self.keys():
			if addMode == defs.noOverwrite:
				raise ISException(valueAlreadyExists, nam)
			if addMode == defs.sum:
				s = self[nam]
				if reNumber.match( s ) and reNumber.match( val ):
					if '.' in s or '.' in val:
						val = str( float( s ) + float( val ) )
					else:
						val = str( int( s ) + int( val ) )
				else:
					val = s + val
		self[nam] = val
		
	def getToken(self, tok):
		'''Returns the SVal container.'''
		path, nam, _ = parse_token(tok, bVal=False)
		
		logtok.debug("[tok: {0}]:  path: {1} ; nam: {2}".format( tok, path, nam))
		
		if not ( nam ):
			raise ISException( unknownDataFormat, tok )
		
		sec = self.getSection( path )
		return sec.getSVal(nam)
	
	def getTokenVal(self, tok):
		'''Returns the token's value.'''
		val = self.getToken(tok).val
		logtok.debug( val )
		return val #self.getToken(tok).val
		
	def getSVal(self, nam):
		if nam not in self.keys():
			raise ISException( objectNotExists, nam )
		return self.get( nam )			
		
	def removeToken(self, tok):
		path, nam, _ = parse_token(tok, bVal=False)
		
		if not ( nam ):
			raise ISException( unknownDataFormat, tok )
		
		sec = self.getSection( path )
		sec.deleteNam(nam) 
		
	def deleteNam(self, nam):
		if nam not in self.keys():
			raise ISException(valueNotExists, nam)
		del self[nam]
		
	def removeSection(self, sec):
		path, _,_ = parse_token(sec, False, False)
		cont = self.getSection(path[0:-1])
		cont.deleteNam(path[-1])
		return
		path, _, nam = sec.rpartition('/')
		cont = self.getSection(path)
		cont.deleteNam( nam )
		
	def copy(self, src, dst, noOverwrite=True ):
		sitem = self.getSItem( src )
		if isinstance( sitem, baseSectType ):
			return self.addSection(sitem)
		elif isinstance(sitem, baseValType):
			return self.addToken(sitem, noOverwrite )
		
	def rename(self, src, dst):
		self.copy(src, dst)
		sitem = self.getSItem(src)
		if isinstance( sitem, baseSectType ):
			return self.removeSection(sitem)
		elif isinstance(sitem, baseValType):
			return self.removeToken(sitem )
		
	def listItems( self, lres, bTree=False, nIndent=0, bNovals=True, relPath=None, bRecur=True ):
		'''This function with btree=False, bNovals=False is used also for writing
		persistent tokens.'''
		if lres == None:
			return
		
		pathPrinted = False if bRecur else True
		
		if bTree:
			# First listing tokens
			for nam, val in self.items():
				if type(val) != type(self):
					if bNovals:
						line = "{0}- {1}".format(' ' * nIndent, nam )
					else:
						line = "{0}- {1}  : {2}".format( ' ' * nIndent, nam, val )
					lres.append( line )
					
			# Then sections				
			for nam, val in self.items():
				if type(val) == type(self):
					line = "{0}[{1}]:".format(' ' * nIndent, nam )
					lres.append( line )
					if bRecur:
						val.listItems( lres=lres, bTree=bTree, nIndent=nIndent + 4, 
									bNovals=bNovals, relPath=relPath, bRecur=bRecur )
					
		else:
			if relPath != None:
				if relPath == '':
					relPath = '.'
				elif relPath == '.':
					relPath = self.name
				else:
					relPath = relPath + "/" + self.name

			for nam, val in self.items():
				if type(val) != type(self):
					if not pathPrinted:
						lres.append("")
						if relPath:
							if relPath != '.':
								lres.append( "[" + relPath + "]")
						else:
							lres.append( "[" + self.pathName() + "]")
						pathPrinted = True
					
					if bNovals:
						line = "{0}".format( nam )
					else:
						nam = nam.replace("=", "\\=")
						line = "{0} = {1}".format( nam, val )
					lres.append( line )
			#res.append("")
			for nam, val in self.items():
				if type(val) == type(self):
					if bRecur:
						val.listItems( lres, bTree, 0, bNovals, relPath, bRecur )
					else:
						lres.append( "[" + val.name + "]")
				
	
	def getTokensList( self, lres ):
		for n, v in self.items():
			if type( v ) == type( self ):
				v.getTokensList( lres )
			else:
				lres.append( self.path + "/" + self.name + "/" + n + "=" + v )
	
	@staticmethod
	def statReg( stok ):
		m=OrderedDict()
		m['num_of_sections'] = stok.numItems( EnumMode.sectionsAll )
		m['num_of_tokens'] = stok.numItems( EnumMode.tokensAll)
		m['max_key_length'] = 0
		m['max_value_length'] = 0
		m['avg_key_length'] = 0
		m['avg_value_length'] = 0
		m['total_size_bytes'] = 0
		stok.enumerate( EnumMode.tokensAll )
		for nam, val in stok:
			if len(nam) > m['max_key_length']:
				m['max_key_length'] = len(nam)
			if len(val) > m['max_value_length']:
				m['max_value_length'] = len(val)
			m['avg_key_length'] += len(nam)
			m['avg_value_length'] += len(val)
			m['total_size_bytes'] += sys.getsizeof(val) + sys.getsizeof(nam)
			
		if m['num_of_tokens']:
			m['avg_key_length'] = round( m['avg_key_length'] / m['num_of_tokens'], 2)
			m['avg_value_length'] = round( m['avg_value_length'] / m['num_of_tokens'], 2 )
		return m
		
def getstor(name='', mode=0o755, gid=None, uid=None):
	return Stor(name=name, mode=mode, gid=gid, uid=uid)

def isPathPers(path):
	if path.startswith( PERSPATH ):
		return True
	else:
		return False

baseSectType = Stor 
baseValType = SVal

def read_tokens_from_lines( lines, stok, addMode=defs.noOverwrite ):
	'''Loads tokens to 'stok' from a string list.'''
	'''Section names must be in square brackets and preceded by an empty line (if not at
	the beginning of the list) in order not to be mixed with tokens like [aaa]=[bbb].'''
	reSect=re.compile(SECTIONPATT)
	reTok=re.compile(TOKENPATT, re.DOTALL)
	reMlTok=re.compile(MULTILINETOKENPATT)
	reEmpty=re.compile("^\s*$")

	curPath = ''
	curTok = None
	
	emptyLine = True
	
	def flush():
		nonlocal curTok, curPath
		if curTok:
			mtok = reTok.match(curTok)
			if not mtok or mtok.lastindex != 2:
				raise ISException(unknownDataFormat, l, "Cannot parse token.")
			stok.addToken( curPath + curTok, addMode )
			curTok = None
			
	for l in lines:
		if reEmpty.match( l ):
			emptyLine = True
			flush()
			continue
		
		m = reSect.match( l )
		if m and emptyLine:
			flush()
			curPath = m.group(1)
			if curPath[-1] != '/': curPath += "/"
			emptyLine = False
			continue
		
		emptyLine = False
		
		m = reMlTok.match(l)
		if m:
			if not curTok:
				raise ISException(unknownDataFormat, l, "Cannot parse token.")
			curTok += stripOne(m.group(1), False, True, '\n')
			continue
		
		flush()
		curTok = stripOne( l, False, True, '\n')
	flush()
				
def read_sec_file( filename, cmd, tok, addMode=defs.noOverwrite ):
	if not os.path.exists( filename ):
		log.error( "Cannot find encrypted data file. Exiting." )
		raise ISException( operationFailed, "File not found." )

	try:
		cmd = cmd.replace( "FILENAME", "{0}" )
		ftxt = subprocess.check_output( cmd.format( filename ),
							shell = True, stderr = subprocess.DEVNULL )
	except subprocess.CalledProcessError as e:
		log.error( ftxt )
		raise ISException( operationFailed, e.output )

	ftxt = ftxt.decode( 'utf-8' )
	ltxt = ftxt.split( "\n" )

	read_tokens_from_lines( ltxt, tok, addMode )
			
def read_tokens_from_file(filename, tok, addMode=defs.noOverwrite ):
	'''Reads tokens from a text file. If the file contains several sections, their names
	should be specified in the file in square brackets in the beginning of each section.
	If tokens are loaded into a single section, its name can be specified either in the 
	file or if the section name is not specified, tokens are loaded into the root section.
	'''
	if not os.path.exists(filename):
		raise ISException(objectNotExists, filename, "File with tokens is not found.")
		
	with open(filename) as f:
		lines = f.readlines()
	
	read_tokens_from_lines(lines, tok, addMode)
				

def read_locked( fd, cp, addMode=defs.noOverwrite ):
	try:
		l = fd.readlines()
		if addMode == defs.overwrite:
			cp.clear()
				
		read_tokens_from_lines(l, cp, addMode )
	except OSError as e:
		raise ISException( operationFailed, e.strerror )
	
def write_locked( fd, tok ):
	from io import SEEK_SET
	try:
		fp = tempfile.TemporaryFile("w+", encoding='utf-8')
		lres = []
		tok.listItems( lres=lres, bTree=False, nIndent=0, bNovals=False, relPath="",
					bRecur=True )
		for ln in lres:
			ln = ln.replace('\n', '\n\t')
			fp.write( ln + "\n")

		fp.flush()
		fp.seek(SEEK_SET, 0)
		s = fp.read()
		fd.seek(SEEK_SET, 0)
		fd.truncate()
		fd.write( s )
		fd.flush()
	except OSError as e:
		raise ISException( operationFailed, e.strerror )
	
# Items manipulation commands (with "Item" or "Section" in name) must receive
# the path argument in the form of directories list.
	
def insertItem( m, path, nam, val, noOverwrite=True):
	curmap = m
	for k in path:
		if k not in curmap:
			curmap[k] = getstor(k)
		curmap = curmap[k]
	if nam in curmap and noOverwrite:
		raise ISException(valueAlreadyExists, "/".join(path) + "/" + nam)
	curmap[nam] = val
	
def getItem( m, path, nam ):
	curmap = m
	for k in path:
		if k not in curmap:
			raise ISException(valueNotExists, k)
		curmap = curmap[k]
	if nam not in curmap:
		raise ISException(valueNotExists, nam)
	return curmap[nam]

def getSection(m, path):
	curmap = m
	for k in path:
		if k not in curmap:
			raise ISException(valueNotExists, k)
		curmap = curmap[k]
	return curmap
			
def removeItem( m, path, num=0):
	if not path:
		return
	key = path[num]
	if key not in m:
		raise ISException(valueNotExists, key)
		
	if len( path ) == num + 1:
		del m[key]
	else:
		curmap = m[key]
		removeItem( curmap, path, num + 1 )	
		if len( curmap ) == 0:
			del m[key]

def getItemsTree(m, l, indent=0):
	for k,v in m.items():
		if isinstance( v, dict):
			l.append( ' '*indent + '[' + k + ']' )
			getItemsTree( m[k], l, indent + 4 )
		else:
			l.append(' '*indent + k + ' = ' + v )
	
def getItemsList( m, l, p=""):
	for k, v in m.items():
		if len( p ):
			curpath = p + '/' + k
		else:
			curpath = "/" + k
		if isinstance( v, dict):
			getItemsList(m[k], l, curpath )
		else:
			l.append( curpath + " = " + v )		
	
def listItems(m, path, l, tree=False):
	if path:
		curmap = getSection( m, path )
	else:
		curmap = m
	
	if tree:
		getItemsTree(curmap, l)
	else:
		getItemsList(curmap, l)

def add_token( cp, tok, noOverwrite=True ):
	path, nam, val = parse_token(tok)
	
	if not ( nam and val ):
		raise ISException( unknownDataFormat, tok ) 

	insertItem(cp, path, nam, val, noOverwrite)

def get_token( cp, tok ):
	path, nam, _ = parse_token( tok, bVal=False )
	
	if not nam:
		raise ISException( unknownDataFormat, tok )

	return getItem(cp, path, nam)

def remove_token( cp, tok ):
	path, nam, _ = parse_token( tok, bVal=False )

	if not nam:
		raise ISException( unknownDataFormat, tok )
	
	removeItem( cp, path + [nam])

def remove_section( cp, sec ):
	path, _, _ = parse_token(sec, bNam=False, bVal=False)
		
	removeItem( cp, path )

def list_tokens( cp, path = None, tree=False ):
	if path:
		path,_,_ = parse_token(path, bNam=False, bVal=False)
	l = []
	listItems(cp, path, l, tree)
	return "\n".join( l )
	
	