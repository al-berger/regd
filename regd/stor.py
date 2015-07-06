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
__lastedited__="2015-07-06 03:45:28"

import re, subprocess, tempfile, os
from regd.util import log, logtok, ISException, unknownDataFormat, operationFailed, \
	objectNotExists, valueAlreadyExists, valueNotExists

GLSEC = "global"
SECTIONPATT="^\[(.*)\]$"
SECTIONNAMEPATT="^(.*?)(?<!\\\):(.*)"
TOKENPATT="^(.*?)(?<!\\\)=(.*)"
MULTILINETOKENPATT="^[ \t](.*)$"

def read_tokens_from_lines( lines, st, pref ):
	reSect=re.compile(SECTIONPATT)
	reTok=re.compile(TOKENPATT, re.DOTALL)
	reMlTok=re.compile(MULTILINETOKENPATT)
	reNonempty=re.compile("(\S.*)")

	if not pref: pref = ""
	curSect = GLSEC
	curTok = None
	
	def flush():
		nonlocal curTok, curSect, st
		if curTok:
			mtok = reTok.match(curTok)
			if mtok.lastindex != 2:
				raise ISException(unknownDataFormat, l, "Cannot parse token.")
			if curSect not in st:
				st[curSect] = {}
			st[curSect][mtok.group(1)] = pref + mtok.group(2)
			curTok = None
			
	for l in lines:
		m = reSect.match(l)
		if m:
			flush()
			curSect = m.group(1)
			continue
		
		m = reMlTok.match(l)
		if m:
			if not curTok:
				raise ISException(unknownDataFormat, l, "Cannot parse token.")
			curTok += m.group(1)
			continue
		
		m = reNonempty.match(l)
		if m:
			flush()
			curTok = m.group(1)
				
def read_sec_file( filename, cmd, tok, sect=None, pref=None ):
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

	m={}
	read_tokens_from_lines(ltxt, m, pref)
	if sect and len( list(m.keys()) ) == 1:
		key = list(m.keys())[0]
		m[sect] = m[key]
		del m[key]
			
def read_tokens_from_file(filename, tok, sect=None, pref=None, overwrite=False):
	'''Reads tokens from a text file. If the file contains several sections, their names
	should be specified in the file in square brackets in the beginning of each section.
	If tokens are loaded into a single section, its name can be specified either in the 
	file, or in the 'sect' parameter (which overrides the section name in the file if it
	exists), or if the section name is not specified, tokens are loaded into 'general' section.
	'''
	if not os.path.exists(filename):
		raise ISException(objectNotExists, filename, "File with tokens is not found.")
		
	with open(filename) as f:
		lines = f.readlines()
	
	m = {}
	read_tokens_from_lines(lines, m, pref)
				
	if sect and len( list(m.keys()) ) == 1:
		key = list(m.keys())[0]
		m[sect] = m[key]
		del m[key]
	
	tok.update( m )

def read_locked( fd, cp, bOverwrite=False ):
	try:
		l = fd.readlines()
		if bOverwrite:
			cp.clear()
				
		read_tokens_from_lines(l, cp, None )
	except OSError as e:
		raise ISException( operationFailed, e.strerror )
	
def write_locked( fd, tok ):
	from io import SEEK_SET
	try:
		fp = tempfile.TemporaryFile("w+", encoding='utf-8')
		#cp.write( fp, True )
		for sectname, sect in tok.items():
			fp.write( "[" + sectname + "]\n")
			for k, v in sect.items():
				tk = k.replace('\n', '\n\t') + " = " + v.replace('\n', '\n\t')
				fp.write( tk )

		fp.flush()
		fp.seek(SEEK_SET, 0)
		s = fp.read()
		fd.seek(SEEK_SET, 0)
		fd.truncate()
		fd.write( s )
		fd.flush()
	except OSError as e:
		raise ISException( operationFailed, e.strerror )
	
def insertItem( m, path, nam, val, noOverwrite=True):
	curmap = m
	for k in path:
		if k not in curmap:
			curmap[k] = {}
		curmap = curmap[k]
	if nam in curmap:
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
		if type( v ) is dict:
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
		if type( v ) is dict:
			getItemsList(m[k], l, curpath )
		else:
			l.append( curpath + "=" + v )		
	
def listItems(m, path, l, tree=False):
	if path:
		curmap = getSection( m, path )
	else:
		curmap = m
	
	if tree:
		getItemsTree(curmap, l)
	else:
		getItemsList(curmap, l)
	

def escaped( s, idx, sym='\\' ):
	'''Determines if a character is escaped'''
	# TODO: I couldn't come up with a reliable way to determine whether a character is 
	# escaped if it's preceded with a backslash: 
	# >>> len('\=')
	# >>> 2
	# >>> len('\\=')
	# >>> 2
	# >>> len('\\a')
	# >>> 2
	# >>> len('\\\a')
	# >>> 2	
	# Because of this there is a rule that separators must not be preceded with a backslash.
	# If an item ends with backslash, a whitespace must be inserted between backslash and
	# separator (this whitespace won't be considered a part of the token). 
	# The same is true if a token ends with whitespace: another white space should be inserted
	# between whitespace and separator. This is for allowing equivalence of two variants:
	# 'a=b' and 'a = b'.
	if not ( s and idx ):
		return False
	
	return ( s[idx-1] is sym )

def stripOne(s, l=False,r=False,ch=' '):
	if not s:
		return s
	if l:
		if s[0] == ch:
			s = s[1:]
	if s and r:
		if s[-1] == ch:
			s = s[:-1]
	return s
	
				
def escapedpart( tok, sep, second=False ):
	'''Partition on non-escaped separators'''
	if not tok:
		return (None, None)
	idx = -1
	start = 1
	while True:
		idx = tok.find( sep, start )
		if ( idx == -1 ) or not escaped(tok, idx): 
			break
		
		start = idx + 1
	
	if idx == -1:
		tok = tok.replace("\\"+sep, sep)
		return (None, tok) if second else ( tok, None )
	
	l, r = ( tok[0:idx], tok[(idx+1):] )
	l = l.replace("\\"+sep, sep)
	#r = r.replace("\\"+sep, sep)
		
	return (l, r)

def parse_token( tok, second=True ):
	logtok.debug( "tok: {0}".format( tok ) )
	path = []
	while True:
		sec, tok = escapedpart( tok, "/", True )
		if sec:
			# One whitespace before and after separator is not part of the token
			sec = stripOne(sec, False, True)
			tok = stripOne(tok, True, False)
			path.append(sec)
		else:
			break

	logtok.debug( "section: {0} : option: {1}".format( "/".join( path ), tok ) )

	if second:
		nam, val = escapedpart(tok, "=")
		nam = stripOne( nam, False, True ) if nam else None
		val = stripOne( val, True, False ) if val else None
	else:
		nam = tok
		val = None

	logtok.debug( "name: {0} = value: {1}".format( nam, val ) )

	if not sec:
		sec = GLSEC
		
	return (path, nam, val)

def add_token( cp, tok, noOverwrite=True ):
	path, nam, val = parse_token(tok)
	
	if not ( nam and val ):
		raise ISException( unknownDataFormat, tok ) 

	insertItem(cp, path, nam, val, noOverwrite)

def get_token( cp, tok ):
	path, nam, _ = parse_token( tok, False )
	
	if not nam:
		raise ISException( unknownDataFormat, tok )

	getItem(cp, path, nam)

def remove_token( cp, tok ):
	path, nam, _ = parse_token( tok, False )

	if not nam:
		raise ISException( unknownDataFormat, tok )
	
	removeItem( cp, path + [nam])

def remove_section( cp, sec ):
	path, _, _ = parse_token(sec, False)
		
	removeItem( cp, path )

def list_tokens( cp, path = None, tree=False ):
	l = []
	listItems(cp, path, l, tree)
	return "\n".join( l )
	
	