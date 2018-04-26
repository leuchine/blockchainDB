import requests
import json
from utils import *
import time
from ethereum.abi import ContractTranslator
from compiler import *
from account import *

#count of calls
count = 0

#url and header
url = "http://localhost:4000/jsonrpc"
headers = {'content-type': 'application/json'}

#create transaction json object
def start_transaction(starter, value, data=None, init=None, to=None):
	global url, headers, count
	payload=None
	if to: #contract call
		payload = {
			"method": "call_transaction",
			"params": [starter, value, encode_data(data), init, encode_data(to)],
			"jsonrpc": "2.0",
			"id": count,
		}
	else: #create contract
		payload = {
			"method": "call_transaction",
			"params": [starter, value, encode_data(data), init],
			"jsonrpc": "2.0",
			"id": count,
		}
	count+=1
	response=requests.post(url, data=json.dumps(payload), headers=headers).json()
	return response

#find the address
def find_address(hashvalue):
	global url, headers, count
	payload=None
	payload = {
		"method": "find_return_value",
		"params": [encode_data(hashvalue)],
		"jsonrpc": "2.0",
		"id": count,
	}
	count+=1
	response=requests.post(url, data=json.dumps(payload), headers=headers).json()
	return response

#get the abi of a contract
# def get_abi(addr):
# 	global url, headers, count
# 	payload=None
# 	payload = {
# 		"method": "find_abi",
# 		"params": [addr],
# 		"jsonrpc": "2.0",
# 		"id": count,
# 	}
# 	count+=1
# 	response=requests.post(url, data=json.dumps(payload), headers=headers).json()
# 	return response

def main():
	#create a contract 
	sourcecode='contract Coin {address public minter; mapping (address => uint) public balances;uint amount;\
	function Coin(uint a) {minter = msg.sender; amount=a;}\
	function mint(address receiver, uint a) payable {\
	if (msg.sender != minter) return;\
	balances[receiver] += a;msg.sender.send(amount);}\
	function send(address receiver, uint amount) {if (balances[msg.sender] < amount) return;\
	balances[msg.sender] -= amount;balances[receiver] += amount;}}'
	#compile the code
	compiler=getCompiler()
	bytecode, contract_interface, translator = compile(compiler, sourcecode)
	starter=0
	value=20
	data=[10]
	encoded_parameters = translator.encode_constructor_arguments(data)
	print('create a new smart contract')
	response=start_transaction(starter, value, encoded_parameters, sourcecode)
	#find the address
	while True:
		hashvalue=hash_transaction(starter, value, encoded_parameters, sourcecode, None, response['result'])
		r=find_address(hashvalue)
		if r['result']!=None:
			break;
		else:
			time.sleep(1)
	print('contract address is:')
	print(encode_data(r['result']))
	#call contract
	response=start_transaction(starter, value, translator.encode('mint', [accounts[2], 90]), None, decode_data(r['result']))
	print(response)

if __name__ == "__main__":
	main()