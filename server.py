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
import requests
import sys

reload(sys)
sys.setdefaultencoding('UTF8')

#waiting for scheduling
waitingqueue=[]
lock = Lock()

#Transaction under execution
executing=[]
executinglocks=[]
#information of executors
executorinfo=[]
#task limit for each executor
limit= 6
#count for executors
count=0
#next executor number
next_executor=0
#submit transaction
@dispatcher.add_method
def call_transaction(starter, value, data=None, init=None, to=None):
	timestamp=time.time()
	global keys, accounts, lock, waitingqueue
	#restore data
	data=decode_data(data)
	to=decode_data(to)
	#put object into waiting queue
	try:
		lock.acquire()
		waitingqueue+=[Transaction(starter, value, data, init, to, timestamp)]
	finally:
		lock.release()
	return timestamp

#find return value of a transaction
@dispatcher.add_method
def find_return_value(hashvalue):
	result=query_log(decode_data(hashvalue))
	if result:
		return encode_data(result)
	else:
		return result

#find abi of a contract
#@dispatcher.add_method
# def find_abi(addr):
# 	print(decode_addr(addr))
# 	result=get_abi(decode_addr(addr))

# 	return result

#pick from waiting queue and submit to executors
def scheduler():
	global waitingqueue
	global lock
	while True:
		if len(waitingqueue)==0:
			time.sleep(0.02)
		else:
			try:
				lock.acquire()
				task=waitingqueue.pop()
			finally:
				lock.release()
			#get hashvalue
			if task.to==None:
				task.hashvalue=hash_transaction(task.starter, task.value, task.data, str(task.init), task.to, task.timestamp)
			else:
				task.hashvalue=hash_transaction(task.starter, task.value, task.data, None, task.to, task.timestamp)
			#pick up executor for running the task
			print("start scheduling for:")
			pick_executor(task)

#pick up executor
# def pick_executor(task):
# 	global executing, limit, executinglocks
# 	while True:
# 		for i in range(len(executorinfo)):
# 			if len(executing[i]) < limit:
# 				try:
# 					executinglocks[i].acquire()
# 					executing[i].append(task)
# 				finally:
# 					executinglocks[i].release()
# 				print('task run on machine:')
# 				print(executorinfo[i])
# 				post_task(i, task)
# 				return
# 		time.sleep(0.02)

def pick_executor(task):
	global executing, limit, executinglocks,next_executor,executorinfo
	next_executor=(next_executor+1)%len(executorinfo)
	print(executorinfo[next_executor])
	post_task(next_executor, task)
	
#post task to executor
def post_task(i, task):
	global count;
	ip, port=executorinfo[i]
	url = "http://"+ip+":"+str(port)+"/jsonrpc"

	headers = {'content-type': 'application/json'}
	payload = {
		"method": "executor",
		"params": [task.starter, task.value, encode_data(task.data), task.init, encode_data(task.to), encode_data(task.hashvalue)],
		"jsonrpc": "2.0",
		"id": count,
	}
	count+=1
	response=requests.post(url, data=json.dumps(payload), headers=headers).json()
	return response


@Request.application
def application(request):
    response = JSONRPCResponseManager.handle(
        request.data, dispatcher)
    return Response(response.json, mimetype='application/json')

#set up information of executors
def executor_info(filename):
	with open(filename, 'r') as f:
		for i in f:
			executor=json.loads(i)
			executing.append([])
			executinglocks.append(Lock())
			executorinfo.append((executor['ip'], executor['port']))

#delete finished tasks from executing:
def delete_finished_task():
	while True:
		for i in range(len(executorinfo)):
			if len(executing[i])!=0:
				try:
					executinglocks[i].acquire()
					for j in range(len(executing[i])):
						
						if query_log(executing[i][j].hashvalue)!=None:
							del executing[i][j]
				finally:
					executinglocks[i].release()

if __name__ == '__main__':
	executor_info('executorlist.txt')
	#start scheduler
	schedulerthread = Thread(target=scheduler)
	schedulerthread.start()
	#start deleter thread
	# deletethread = Thread(target=delete_finished_task)
	# deletethread.start()
	#json rpc service for client
	run_simple('localhost', 4000, application)