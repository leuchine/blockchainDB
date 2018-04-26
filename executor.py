from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple
from jsonrpc import JSONRPCResponseManager, dispatcher
from account import *
import time
import json
from ethereum.ethash_utils import *
from rlp.utils import decode_hex, encode_hex, ascii_chr
from threading import *
import vm
from utils import *
from databaseconnect import *
from utils import *
import sys

reload(sys)
sys.setdefaultencoding('UTF8')

#submit transaction
@dispatcher.add_method
def executor(starter, value, data, init, to, hashvalue):
	#decode data
	data=decode_data(data)
	to=decode_data(to)
	hashvalue=decode_data(hashvalue)
			
	print('start executing:'+str(encode_data(hashvalue)))
	if to==None:
		func=vm.contract_creation
	else:
		func=vm.contract_call

	t = Thread(target=func, args=[Transaction(starter, value, data, init, to), hashvalue])
	t.start()
	return True

@Request.application
def application(request):
    response = JSONRPCResponseManager.handle(
        request.data, dispatcher)
    return Response(response.json, mimetype='application/json')

if __name__ == '__main__':
	#json rpc service for server
	run_simple('localhost', 8000, application)