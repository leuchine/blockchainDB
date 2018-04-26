from compiler import *
from databaseconnect import *
import opcodes
import copy
from ethereum import utils
from rlp.utils import decode_hex, encode_hex, ascii_chr
from ethereum.utils import safe_ord
import processmessage
import time
import account
from account import *

TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1

#data field of a transaction
class CallData(object):

    def __init__(self, parent_memory, offset=0, size=None, originaldata=None):
        self.data = parent_memory
        self.offset = offset
        self.size = len(self.data) if size is None else size
        self.rlimit = self.offset + self.size
        self.originaldata=originaldata

    def extract32(self, i):
        if i >= self.size:
            return 0
        o = self.data[self.offset + i: min(self.offset + i + 32, self.rlimit)]
        return utils.bytearray_to_int(o + [0] * (32 - len(o)))

#A transaction
class Message(object):

    def __init__(self, sender, to, value, data,
            code_address=None, transfers_value=True, timestamp=None, abi=None, h=None):
        self.sender = sender
        self.to = to
        self.value = value
        self.data = data
        self.code_address = code_address
        self.transfers_value=transfers_value
        self.abi=abi
        #set the timestamp of the message
        if timestamp==None:
        	timestamp=time.time()
        self.timestamp=timestamp
        self.hash=h
#Encapsulate virtual machine state
class Compustate():

    def __init__(self):
        self.memory = []
        self.stack = []
        self.pc = 0

# Preprocesses code to readable format
def preprocess_code(code):
    assert isinstance(code, bytes)
    code = memoryview(code).tolist()
    ops = []
    i = 0
    while i < len(code):
        o = copy.copy(opcodes.opcodes.get(code[i], ['INVALID', 0, 0, 0]) + [code[i], 0])
        ops.append(o)
        if o[0][:4] == 'PUSH':
            for j in range(int(o[0][4:])):
                i += 1
                byte = code[i] if i < len(code) else 0
                o[-1] = (o[-1] << 8) + byte
                if i < len(code):
                    ops.append(['INVALID', 0, 0, 0, byte, 0])
        i += 1
    return ops

#roll back transaction
def rollback(connection, s):
	return (s, None)

#extend memory to a larger size. The unit is byte
def mem_extend(mem, compustate, op, start, sz):
    if sz:
        oldsize = len(mem) // 32        
        newsize = utils.ceil32(start + sz) // 32    
        if oldsize < newsize:
            m_extend = (newsize - oldsize) * 32
            mem.extend([0] * m_extend)
    return True

#return success signal
def success(connection, list):
	return ('SUCCESS', list)

#Execute smart contract bytecode
def execute(code, msg, connection):

	#do nothing if no code
	if code==None:
		return ('SUCCESS', None)

	#build up execution environment
	compustate = Compustate()
	stk = compustate.stack
	mem = compustate.memory
	#process code (byte to list)
	processed_code=preprocess_code(code)
	codelen = len(processed_code)

	while 1:
		if compustate.pc >= codelen:
			break
		#print code to be executed
		#print("PC:"+str(compustate.pc))
		#print(processed_code[compustate.pc])
		op, in_args, out_args, fee, opcode, pushval = processed_code[compustate.pc]
		if in_args > len(compustate.stack):
			return rollback(connection, "INSUFFICIENT STACK")
		if len(compustate.stack) - in_args + out_args > 1024:
			return rollback(connection, "STACK SIZE LIMIT EXCEEDED")
		compustate.pc += 1
		if op == 'INVALID':
			return rollback(connection, "INVALID OP")
		#run one opcode here
		if opcode < 0x10:
			if op == 'STOP':
				return success(connection, [])
			elif op == 'ADD':
				stk.append((stk.pop() + stk.pop()) & TT256M1)
			elif op == 'SUB':
				stk.append((stk.pop() - stk.pop()) & TT256M1)
			elif op == 'MUL':
				stk.append((stk.pop() * stk.pop()) & TT256M1)
			elif op == 'DIV':
				s0, s1 = stk.pop(), stk.pop()
				stk.append(0 if s1 == 0 else s0 // s1)
			elif op == 'MOD':
				s0, s1 = stk.pop(), stk.pop()
				stk.append(0 if s1 == 0 else s0 % s1)
			elif op == 'EXP':
				base, exponent = stk.pop(), stk.pop()
				stk.append(pow(base, exponent, TT256))
		elif opcode < 0x20:
			if op == 'LT':
				stk.append(1 if stk.pop() < stk.pop() else 0)
			elif op == 'GT':
				stk.append(1 if stk.pop() > stk.pop() else 0)
			elif op == 'EQ':
				stk.append(1 if stk.pop() == stk.pop() else 0)
			elif op == 'ISZERO':
				stk.append(0 if stk.pop() else 1)
			elif op == 'AND':
				stk.append(stk.pop() & stk.pop())
			elif op == 'OR':
				stk.append(stk.pop() | stk.pop())
			elif op == 'XOR':
				stk.append(stk.pop() ^ stk.pop())
			elif op == 'NOT':
				stk.append(TT256M1 - stk.pop())
		elif opcode < 0x40:
			if op == 'SHA3':
				s0, s1 = stk.pop(), stk.pop()
				if not mem_extend(mem, compustate, op, s0, s1):
				    return rollback(connection, "EXTEND MEMORY ERROR")
				data = b''.join(map(ascii_chr, mem[s0: s0 + s1]))
				stk.append(utils.big_endian_to_int(utils.sha3(data)))
			elif op == 'CALLER':
				stk.append(utils.coerce_to_int(msg.sender))
			elif op == 'CALLVALUE':
				stk.append(msg.value)
			#load data from calling parameter
			elif op == 'CALLDATALOAD':
				stk.append(msg.data.extract32(stk.pop()))
			#copy code (size s1), start: in memory, s1: in code
			elif op == 'CALLDATASIZE':
				stk.append(msg.data.size)
			elif op == 'CODECOPY':
				start, s1, size = stk.pop(), stk.pop(), stk.pop()
				if not mem_extend(mem, compustate, op, start, size):
					return rollback(connection, "EXTEND MEMORY ERROR")
				for i in range(size):
					if s1 + i < len(processed_code):
						mem[start + i] = processed_code[s1 + i][4]
					else:
						mem[start + i] = 0				
		elif opcode < 0x50:
			pass
		elif opcode < 0x60:
			if op == 'POP':
				stk.pop()
			#load memory position s0 to stack
			elif op == 'MLOAD':
				s0 = stk.pop()
				if not mem_extend(mem, compustate, op, s0, 32):
					return rollback(connection, "EXTEND MEMORY ERROR")
				data = b''.join(map(ascii_chr, mem[s0: s0 + 32]))
				stk.append(utils.big_endian_to_int(data))
			#store s1 (32 bytes) to position s0
			elif op == 'MSTORE':
				s0, s1 = stk.pop(), stk.pop()
				if not mem_extend(mem, compustate, op, s0, 32):
					return rollback(connection, "EXTEND MEMORY ERROR")
				v = s1
				for i in range(31, -1, -1):
					mem[s0 + i] = v % 256
					v //= 256
			elif op == 'SLOAD':
				stk.append(get_storage_data(connection, msg.to, stk.pop()))
			elif op == 'SSTORE':
				s0, s1 = stk.pop(), stk.pop()
				set_storage_data(connection, msg.to, s0, s1, msg.hash)

			elif op == 'JUMP':
				compustate.pc = stk.pop()
				opnew = processed_code[compustate.pc][0] if \
				compustate.pc < len(processed_code) else 'STOP'
				if opnew != 'JUMPDEST':
					return rollback(connection, 'JUMP BAD JUMPDEST')
			elif op == 'JUMPI':
				s0, s1 = stk.pop(), stk.pop()
				if s1:
					compustate.pc = s0
					opnew = processed_code[compustate.pc][0] if \
						compustate.pc < len(processed_code) else 'STOP'
					if opnew != 'JUMPDEST':
						return rollback(connection, 'JUMPI BAD JUMPDEST')
		elif op[:4] == 'PUSH':
			pushnum = int(op[4:])
			compustate.pc += pushnum
			stk.append(pushval)
		elif op[:3] == 'DUP':
			depth = int(op[3:])
			stk.append(stk[-depth])
		elif op[:4] == 'SWAP':
			depth = int(op[4:])
			temp = stk[-depth - 1]
			stk[-depth - 1] = stk[-1]
			stk[-1] = temp
		elif op == 'CALL':
			gas, to, value, meminstart, meminsz, memoutstart, memoutsz = \
			stk.pop(), stk.pop(), stk.pop(), stk.pop(), stk.pop(), stk.pop(), stk.pop()

			if not mem_extend(mem, compustate, op, meminstart, meminsz) or \
			not mem_extend(mem, compustate, op, memoutstart, memoutsz):
				return rollback(connection, "EXTEND MEMORY ERROR")
			to = utils.encode_int(to)
			to = ((b'\x00' * (32 - len(to))) + to)[12:]

			if get_balance(connection,msg.to) >= value:
				calld = CallData(mem, meminstart, meminsz, originaldata=str(mem[meminstart: meminstart+meminsz]))
				call_msg = Message(msg.to, to, value, calld, code_address=to, h=msg.hash)
				insert_associatedtx(call_msg, connection)
				result, data = processmessage._apply_msg(call_msg, get_code(connection, to), connection)
				
				if data==None:
					data=''
				if result == 'SUCCESS':
					stk.append(1)
					for i in range(min(len(data), memoutsz)):
						mem[memoutstart + i] = data[i]						
				else:
					stk.append(0)
			else:
				stk.append(0)
		elif op == 'RETURN':
			s0, s1 = stk.pop(), stk.pop()
			
			if not mem_extend(mem, compustate, op, s0, s1):
				return rollback(connection, "EXTEND MEMORY ERROR")
			return success(connection, mem[s0: s0 + s1])
		#status after execution
		#print(hexoutput(compustate.stack))
		#print(hexoutput(compustate.memory)) 
		#print('------------------------------------')

#execute contract creation
def contract_creation(trans, hashvalue):
	print('new contract')
	print(len(hashvalue))
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, trans.init)
	bytecode+=trans.data

	message = Message(account.accounts[trans.starter], trans.to, trans.value, \
		bytecode, code_address=None, timestamp=trans.timestamp, abi=contract_interface, h=hashvalue)
	result=processmessage.apply_transaction(message)	

#execute contract calling
def contract_call(trans, hashvalue):
	print("new message call")
	print(len(hashvalue))
	message_data = CallData([safe_ord(x) for x in trans.data], 0, None, originaldata=trans.data)

	message = Message(account.accounts[trans.starter], trans.to, trans.value, message_data, code_address=trans.to, h=hashvalue)
	processmessage.apply_transaction(message)

#Main function
if __name__ == "__main__":
	#contract creation
	# sourcecode='contract SimpleStorage {uint storedData; \
	# function SimpleStorage(){}\
	# function set(uint x) {storedData = x;}\
	# function get() constant returns (uint retVal) {return storedData;}}'
	sourcecode='contract Coin {address public minter; mapping (address => uint) public balances;uint amount;\
	function Coin(uint a) {minter = msg.sender; amount=a;}\
	function mint(address receiver, uint a) payable {\
	if (msg.sender != minter) return;\
	balances[receiver] += a;msg.sender.send(amount);}\
	function send(address receiver, uint amount) {if (balances[msg.sender] < amount) return;\
	balances[msg.sender] -= amount;balances[receiver] += amount;}}'
	
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, sourcecode)
	encoded_parameters = translator.encode_constructor_arguments([10])	
	bytecode+=encoded_parameters
	message = Message(accounts[0], None, 50, bytecode, code_address=None, timestamp=time.time(), abi=contract_interface, h='s24a2')
	result=processmessage.apply_transaction(message)
	print(result)

	#function call
	address=result[1]
	for function_name in translator.function_data:
		if function_name=='mint':
			message_data = CallData([safe_ord(x) for x in translator.encode(function_name, [accounts[2], 90])], 0, None)

			message = Message(accounts[0], address, 20, message_data, code_address=address, h='2333')
			print(processmessage.apply_transaction(message))

		# if function_name=='send':
		# 	message_data = CallData([safe_ord(x) for x in translator.encode(function_name, ['\xa0\xfc\x04\xfa-4\xa6kw\x9f\xd5\xce\xe7H&\x802\xa1F\xc0', 20])], 0, None)
		# 	message = Message('\xe0\xfc\x04\xfa-4\xa6kw\x9f\xd5\xce\xe7H&\x802\xa1F\xc0', address, 0, message_data, code_address=address)
		# 	print(processmessage.apply_transaction(message))