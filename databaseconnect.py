import mysql.connector

#connect to local MySQL
def connect_MySQL():
	connection = mysql.connector.connect(user='root',\
		password='123456', host='127.0.0.1',database='mysql')
	return connection

