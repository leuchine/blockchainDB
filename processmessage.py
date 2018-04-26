import vm
from vm import *
from databaseconnect import *
from ethereum.utils import sha3
from rlp.utils import ascii_chr
import rlp
from utils import *

#apply message and code on blockchain
def _apply_msg(msg, code, connection):
    # Transfer value, quit if not enough
    if msg.transfers_value and msg.value>=0:
        if not transfer_value(connection, msg.sender, msg.to, msg.value, msg.hash):
            print("TRANSFER FAIL")
            return "TRANSFER FAIL", []
    print(encode_data(msg.sender)+" send to "+encode_data(msg.to)+": "+ str(msg.value))
    # Execute the message on virtual machine
    result, data = vm.execute(code, msg, connection)

    return result, data

#process transaction, encapsulate Virtual Machine.
def apply_transaction(message):
    #database connection
    connection=connect_Azure()
    insert_transaction(message, connection)
    #cursor.execute("BEGIN TRANSACTION")

    #record which function used
    flag=True
    if message.to: #Contract calling
        result, data = _apply_msg(message, get_code(connection, message.to), connection)
    else:  # CREATE
        flag=False
        result, data = create_contract(message, connection)
    print(result)

    if result!='SUCCESS':
        #roll back transaction
        connection.rollback()
        output = b''
        #insert progress
        insert_log(message.hash, result, connection)
        connection.commit()
        connection.close()
        return result, output  
    if flag: #calling
        output = b''.join(map(ascii_chr, data))
    else: #create
        output = message.to
        insert_code(message.to, data, message.abi,connection)
    #insert output into database
    insert_log(message.hash, output, connection)
    #commit transaction
    connection.commit()
    connection.close()

    return result, output

#create new contract
def create_contract(msg, connection):
    sender = msg.sender
    code = msg.data
    #create address for a new contract
    msg.to = mk_contract_address(sender, msg.timestamp)
    print("create contract:")
    print(encode_hex(msg.to))
    #create contract
    msg.data = vm.CallData([], 0, 0)
    res, dat = _apply_msg(msg, code, connection)
    return res, dat

#create new address for contract
def mk_contract_address(sender, timestamp):
    return sha3(rlp.encode([sender, str(timestamp)]))[12:]