from compiler import *
from databaseconnect import *
import opcodes
import copy
from ethereum import utils
from rlp.utils import decode_hex, encode_hex
from ethereum.utils import safe_ord

TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1

#data field of a transaction
class CallData(object):

    def __init__(self, parent_memory, offset=0, size=None):
        self.data = parent_memory
        self.offset = offset
        self.size = len(self.data) if size is None else size
        self.rlimit = self.offset + self.size

    def extract32(self, i):
        if i >= self.size:
            return 0
        o = self.data[self.offset + i: min(self.offset + i + 32, self.rlimit)]
        return utils.bytearray_to_int(o + [0] * (32 - len(o)))

#A transaction
class Message(object):

    def __init__(self, sender, to, value, data,
            code_address=None):
        self.sender = sender
        self.to = to
        self.value = value
        self.data = data
        self.code_address = code_address


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
	connection.rollback()
	connection.close()
	return s

#extend memory to a larger size. The unit is byte
def mem_extend(mem, compustate, op, start, sz):
    if sz:
        oldsize = len(mem) // 32        
        newsize = utils.ceil32(start + sz) // 32    
        if oldsize < newsize:
            m_extend = (newsize - oldsize) * 32
            mem.extend([0] * m_extend)
    return True

def success(connection, list):
	connection.commit()
	connection.close()
	return list

#Execute smart contract bytecode
def execute(code, msg):
	connection=connect_MySQL()
	#Use transaction for safety
	connection.start_transaction(isolation_level='SERIALIZABLE')

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
		print("PC:"+str(compustate.pc))
		print(processed_code[compustate.pc])
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
			if op == 'EQ':
				stk.append(1 if stk.pop() == stk.pop() else 0)
		elif opcode < 0x40:
			if op == 'SHA3':
				pass
			elif op == 'CALLVALUE':
				stk.append(msg.value)
			elif op == 'CALLDATALOAD':
				stk.append(msg.data.extract32(stk.pop()))
			#copy code (size s1), start: in memory, s1: in code
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
				set_storage_data(connection, msg.to, s0, s1)

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
		elif op == 'RETURN':
			s0, s1 = stk.pop(), stk.pop()
			if not mem_extend(mem, compustate, op, s0, s1):
				return rollback(connection, "EXTEND MEMORY ERROR")
			return success(connection, mem[s0: s0 + s1])
		#status after execution
		print(hexoutput(compustate.stack))
		print(hexoutput(compustate.memory)) 
		print('------------------------------------')

#hex format output
def hexoutput(list):
	return [hex(j) for j in list ]

#encode result from contract creation to bytecode
def memory2bytecode(list):
	return ''.join([chr(i) for i in list])
#Main function
if __name__ == "__main__":
	#contract creation
	# sourcecode='contract SimpleStorage {uint storedData; \
	# function SimpleStorage(){}\
	# function set(uint x) {storedData = x;}\
	# function get() constant returns (uint retVal) {return storedData;}}'
	sourcecode='contract Coin {address public minter; mapping (address => uint) public balances;\
	function Coin() {minter = msg.sender;}\
	function mint(address receiver, uint amount) {\
	if (msg.sender != minter) return;\
	balances[receiver] += amount;}\
	function send(address receiver, uint amount) {if (balances[msg.sender] < amount) return;\
	balances[msg.sender] -= amount;balances[receiver] += amount;}}'
	
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, sourcecode)
	result=execute(bytecode, None)
	print(hexoutput(result))
	#function call
	newcode=memory2bytecode(result)
	for function_name in translator.function_data:
		if function_name=='set':
			message_data = CallData([safe_ord(x) for x in translator.encode(function_name, [10])], 0, len(translator.encode(function_name, [10])))
			message = Message('a', 'b', 0, message_data, code_address='b')
			print(execute(newcode, message))
		if function_name=='get':
			message_data = CallData([safe_ord(x) for x in translator.encode(function_name, [])], 0, len(translator.encode(function_name, [])))
			message = Message('a', 'b', 0, message_data, code_address='b')
			print(execute(newcode, message)) 