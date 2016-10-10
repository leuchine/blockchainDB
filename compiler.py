from ethereum._solidity import get_solidity
from rlp.utils import decode_hex, encode_hex
from ethereum.abi import ContractTranslator

#Get the compiler of Solidity
def getCompiler():
	compiler = None
	_solidity = get_solidity()
	if _solidity:
	    compiler = _solidity
	return compiler

#Compile from sourcecode(String) and get ABI. Online demo:
#https://ethereum.github.io/browser-solidity/#version=soljson-v0.4.2+commit.af6afb04.js&optimize=true
def compile(compiler, sourcecode):
	bytecode = compiler.compile(sourcecode, path=None, libraries=None)
	contract_interface = compiler.mk_full_signature(sourcecode, path=None)
	
	translator = ContractTranslator(contract_interface)
	print('Hex sourcecode:')
#	print(bytecode)
	print(encode_hex(bytecode))
#	print('ABI:')
#	print(contract_interface)
	return bytecode, contract_interface, translator

#Main function
if __name__ == "__main__":
	sourcecode='contract SimpleStorage {uint storedData; \
	function SimpleStorage(){}\
	function set(uint x) {storedData = x;}\
	function get() constant returns (uint retVal) {return storedData;}}'
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, sourcecode)
