from compiler import *
from databaseconnect import *
import opcodes
import copy

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

#Execute smart contract bytecode
def execute(code):
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
		op, in_args, out_args, fee, opcode, pushval = \
		processed_code[compustate.pc]
		if in_args > len(compustate.stack):
			return rollback(connection, "INSUFFICIENT STACK")
		if len(compustate.stack) - in_args + out_args > 1024:
			return rollback(connection, "STACK SIZE LIMIT EXCEEDED")
		compustate.pc += 1
		if op == 'INVALID':
			return rollback(connection, "INVALID OP")
		#run one opcode here
		if opcode < 0x10:
			pass
		elif opcode < 0x20:
			pass
		elif opcode < 0x40:
			pass
		elif opcode < 0x50:
			pass
		elif opcode < 0x60:
			pass
		elif op[:4] == 'PUSH':
			pushnum = int(op[4:])
			compustate.pc += pushnum
			stk.append(pushval)
        print(compustate.stack)
        print(compustate.memory)  
	connection.commit()
	connection.close()

#Main function
if __name__ == "__main__":
	sourcecode='contract SimpleStorage {uint storedData; \
	function SimpleStorage(){}\
	function set(uint x) {storedData = x;}\
	function get() constant returns (uint retVal) {return storedData;}}'
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, sourcecode)
	execute(bytecode)

