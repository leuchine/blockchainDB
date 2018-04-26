from ethereum.utils import to_string, sha3, privtoaddr
from databaseconnect import *
#store private keys
keys=[]
#store pulbic address
accounts=[]
#account total number
account_total=100

for account_number in range(account_total):
    keys.append(sha3(to_string(account_number)))
    accounts.append(privtoaddr(keys[-1]))


if __name__ == "__main__":
	for i in accounts:
		insert_account(i, 100000)