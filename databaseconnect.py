import mysql.connector

#connect to local MySQL
def connect_MySQL():
	connection = mysql.connector.connect(user='root',\
		password='123456', host='127.0.0.1',database='blockchain')
	return connection

#set data in storage table
def set_storage_data(connection, address, item, value):
	insert= ("INSERT INTO storage "
               "(address, item, value, time) "
               "VALUES (%s, %s, %s, NOW()) ON DUPLICATE KEY UPDATE value=%s, time=NOW()")
	data= (address, str(item), str(value), str(value))

	cursor = connection.cursor()
	cursor.execute(insert, data)
	cursor.close()

#get data in storage table
def get_storage_data(connection, address, item):
	query= ("SELECT value FROM storage "
               "WHERE address=%s and item=%s")
	data=(address,item)
	cursor = connection.cursor()
	cursor.execute(query, data)
	for value in cursor:
		cursor.close()		
		return int(value[0])
	cursor.close()
	return 0