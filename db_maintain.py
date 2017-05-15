import os
import pickle
from urlparse import urlparse
import psycopg2

styleguide = pickle.load(open('style_guide'))

url = urlparse(os.environ["DATABASE_URL"])
conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cur = conn.cursor()

def create_table():
    '''makes table'''
    cur.execute("CREATE TABLE horace (term varchar, definition varchar);")

def insert_dict(sguide):
    '''add existing dictionary to table'''
    terms = list(sguide.keys())
    definitions = list(sguide.values())

    sgdict = zip(terms, definitions)

    for i in sgdict:
        cur.execute("INSERT INTO horace VALUES (%s, %s)", [i])

create_table()
insert_dict(styleguide)
