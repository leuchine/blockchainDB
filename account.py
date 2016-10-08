from ethereum.utils import to_string, sha3, privtoaddr

#store private keys
keys=[]
#store pulbic address
accounts=[]
#account total number
account_total=10

for account_number in range(account_total):
    keys.append(sha3(to_string(account_number)))
    accounts.append(privtoaddr(keys[-1]))
# print(keys)
# print(len(keys))
# print(accounts)
# print(len(accounts))