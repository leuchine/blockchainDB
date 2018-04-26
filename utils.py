from rlp.utils import decode_hex, encode_hex, ascii_chr
import account
import sys
from ethereum.utils import sha3
reload(sys)  # Reload does the trick!
sys.setdefaultencoding('UTF8')

#hex format output
def hexoutput(l):
	if len(l)==0:
		return []
	if isinstance(l[0], str):
		
		return [encode_hex(j) for j in l]
	else:

		return [hex(j) for j in l]

#encode result from contract creation to bytecode
def memory2bytecode(list):
	return ''.join([chr(i) for i in list])

#hash transaction using sha3
def hash_transaction(starter, value, data, init, to, timestamp):
	global accounts
	representation=account.accounts[starter]+str(value)
	if data != None:
		representation+=repr(data)
	if init != None:
		representation+=repr(init)
	if to != None:
		representation+=to
	representation+=repr(timestamp)
	return sha3(representation)[:90]

#for json-rpc communication
def encode_data(s):
	if s==None:
		return s
	return encode_hex(s)
	
#for json-rpc communication
def decode_data(s):
	if s==None:
		return s
	return decode_hex(str(s))

class Transaction:
	def __init__(self,starter, value, data, init, to, timestamp=None):
		self.starter=starter
		self.value=value
		self.data=data
		self.init=init
		self.to=to
		self.timestamp=timestamp