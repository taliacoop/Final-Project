import sqlite3
import requests
import unittest
import json

#loop through list of codes to gwet data from multiple airports
airport_token = "ed02a573426401a69f4c65fc9dd6f0dc6520a42fbe89033ceecdda9669dc7b75740fb606ee40ac376fea9bcba77b8e47"

def create_database():
    airport_list = ["KJFK", "KLAX", "KEWR", "KDTW"]
    for airport in airport_list:

        url = 'https://airportdb.io/api/v1/airport/' + airport + '?apiToken='+ airport_token
        resp = requests.get(url)
        
        if resp.status_code == 200:
        
            data = json.loads(resp.text)
            print(data)
        else:
            print("invalid url")
    db_airport_file = "airport.db"
    conn = sqlite3.connect(db_airport_file)
    cursor = conn.cursor()


    create_table
# decide what tables youre going to make and what columns they are going to have

#create multiple tables within the database from dictionary
# there should be no duplicate strings ... if there are, link them with an id
# should only be gathering 25 items at a time, must be new data everytime, 
# would need to run 4 times so you get 100 items total from EACH API
# can do this by checking first if the (type,id, table, etc) exists if os.path.exist(filename).......


# use long+lat from airport databse to gather information from weather.gov.api


        
def main():
    create_database()

if __name__ == '__main__':
    main()



