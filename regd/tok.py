'''
/********************************************************************
*	Module:			regd.iter
*
*	Created:		Jul 9, 2015
*
*	Abstract:		Iterators.
*
*	Author:			Albert Berger [ alberger@gmail.com ].
*		
*********************************************************************/
'''
__lastedited__="2015-12-01 04:03:25"

from regd.util import logtok, ISException, unknownDataFormat
import regd.util as util

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
	# If an item ends with backslash, a whitespace must be inserted between the backslash and
	# the separator (this whitespace won't be considered a part of the token). 
	# The same is true if a token part ends with whitespace: another white space should be 
	# inserted between the whitespace and separator. This is for allowing the equivalence of 
	# two variants: 'a=b' and 'a = b'.
	if not ( s and idx ):
		return False
	
	return ( s[idx-1] is sym )

def escapedpart( tok, sep, second=False ):
	'''Partition on non-escaped separators'''
	if not tok:
		return (None, None)
	idx = -1
	start = 0
	
	# Special case: separator as the first character
	if tok[0] == sep:
		tok = tok[1:]
		return ('', tok)
		
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

def parse_token( tok_, bNam=True, bVal=True ):
	tok = tok_
	logtok.debug( "tok: {0}".format( tok ) )
	path = []
	while True:
		#sec, tok = escapedpart( tok, "/", bNam )
		# Slashes are not allowed in section names
		sec,_,tok = tok.partition('/')
		if not tok and sec and bNam:
			tok = sec
			sec = None
		
		if sec != None:
			# Null character as a subdirectory name is not allowed 
			if not len( sec ) and len( path ):
				if tok:
					raise ISException(unknownDataFormat, tok_, "Null character as a section name.")
				break
			# One whitespace before and after separator is not part of the token
			sec = stripOne(sec, False, True)
			tok = stripOne(tok, True, False)
			path.append(sec)
		else:
			break

	logtok.debug( "section: {0} : option: {1}".format( "/".join( path ), tok ) )

	if bVal:
		nam, val = escapedpart(tok, "=")
		nam = stripOne( nam, False, True ) if nam else None
		val = stripOne( val, True, False ) if val else None
	else:
		nam = tok.replace( "\\=", "=")
		val = None

	logtok.debug( "name: {0} = value: {1}".format( nam, val ) )
		
	return (path, nam, val)

class TokenFeeder:
	modeToken 	= 1
	modeKeyVal 	= 2
	modeKey 	= 3
	modeTokenB 	= 4
	modeKeyValB = 5
	modeKeyB 	= 6
	
	class TFit:
		def __init__(self, tf, binary=False):
			self.cnt = 0
			self.tf = tf
			self.binary = binary
	
	class TokenIt(TFit):
		def __init__(self, tf, binary=False):
			super(TokenFeeder.TokenIt, self).__init__(tf, binary)
		
		def __next__(self):
			if self.binary:
				tk = self.tf.getTokenB( self.cnt )
				tok = tk[0][0] + bytes(b' /') + tk[0][1] + bytes(b' =') + tk[0][2]
				tok = (tok, tk[1])
			else:
				tk = self.tf.getToken( self.cnt )
				tok = ( tk[0][0]+" /"+tk[0][1]+" ="+tk[0][2], tk[1] )
				
			self.cnt += 1
			return tok
		
	class KeyValIt(TFit):
		def __init__(self, tf, binary=False):
			super(TokenFeeder.KeyValIt, self).__init__(tf, binary)
		
		def __next__(self):
			if self.binary:
				tok = self.tf.getTokenB( self.cnt )
				key = ((tok[0][0] + bytes(b' /')) if tok[0][0] else b"") + tok[0][1]
				val = tok[0][2]
			else:
				tok = self.tf.getToken( self.cnt )
				key = ((tok[0][0] + ' /') if tok[0][0] else "") + tok[0][1]
				val = tok[0][2]
				
			self.cnt += 1
			return ( key, val, tok[1] )
		
	class KeyIt(TFit):
		def __init__(self, tf, binary=False):
			super(TokenFeeder.KeyIt, self).__init__(tf, binary)
		
		def __next__(self):
			if self.binary:
				tok = self.tf.getTokenB( self.cnt )
				key = tok[0][0] + bytes(b' /') + tok[0][1]
			else:
				tok = self.tf.getToken( self.cnt )
				key = tok[0][0] + ' /' + tok[0][1]
				
			self.cnt += 1
			return ( key, tok[1] )
	
	def __init__( self, parts, bparts=None, num = None ):
		'''parts - list of stringised tokens: '/path/nam=val' '''
		self.parts = parts
		if bparts:
			self.bparts = bparts
		else:
			self.bparts = [p.encode('utf-8') for p in parts]
		self.n = len( parts )
		self.mode = TokenFeeder.modeToken
		self.num = 0
		self.num = num if num != None and num < self.__len__() and num > 0 else self.__len__()

	def __iter__( self ):
		if self.mode == TokenFeeder.modeToken:
			return TokenFeeder.TokenIt( self )
		elif self.mode == TokenFeeder.modeKeyVal:
			return TokenFeeder.KeyValIt( self )
		elif self.mode == TokenFeeder.modeKey:
			return TokenFeeder.KeyIt( self )

	def __len__( self ):
		return len(self.parts)
	
	def getToken( self, cnt ):
		if cnt >= self.__len__():
			raise StopIteration()
		tok = self.parts[cnt]
		path, nam, val =  parse_token(tok, True, True)
		cur = "{0} ({1})".format( tok, cnt )
		return ( ( "/".join(path), nam, val ), cur )
	
	def getTokenB( self, cnt ):
		if cnt >= self.__len__():
			raise StopIteration()
		tok = self.bparts[cnt]
		path, nam, val =  parse_token(tok, True, True)
		cur = "{0} ({1})".format( tok, cnt )
		return ( ( "/".join(path), nam, val ), cur )
	
	def setMode( self, mode ):
		if mode < 1 or mode > 6:
			raise util.ISException(util.unrecognizedParameter)
		self.mode = mode


	
class TokenStringFeeder(TokenFeeder):
	def __init__(self, parts, num=None):
		bparts = [p.encode('utf-8') for p in parts]
		super(TokenStringFeeder, self).__init__(parts, bparts, num)
		
	def __len__( self ):
		return len(self.parts)
	
	def getToken(self, cnt):
		if cnt >= self.__len__():
			raise StopIteration()
		ni = cnt % self.n
		vi = (cnt // self.n ) % self.n
		si2 = (cnt // self.n) % self.n 
		si1 = (cnt // self.n ** 2 ) % self.n
		s1 = self.parts[si1]
		s2 = self.parts[si2]
		n = self.parts[ni]
		v = self.parts[vi]
		cur = "{0}-{1}-{2}-{3} ({4})".format( si1, si2, ni, vi, cnt )
		return ( ( s1 + " /" + s2, n, v ), cur )
	
	def getTokenB( self, cnt ):
		if cnt >= self.__len__():
			raise StopIteration()
		si1 = cnt // self.n
		si2 = cnt % self.n
		ni = cnt % self.n
		vi = cnt // self.n
		s1 = bytearray( self.bparts[si1] )
		s2 = bytearray( self.bparts[si2] )
		n = bytearray ( self.bparts[ni] )
		v = bytearray( self.bparts[vi] )
		s = s1
		s.append(b'\x32')
		s.append(b'\x92')
		s.extend(s2)
		
		cur = "{0}-{1}-{2}-{3} ({4})".format( si1, si2, ni, vi, cnt )
		return ( ( s, n, v ), cur )	