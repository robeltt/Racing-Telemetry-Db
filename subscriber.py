import os
import json

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import mysql.connector
from pymongo import MongoClient
from neo4j import GraphDatabase

from riders import RIDERS

load_dotenv()                             


MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))

mongo_db = None
mysql_conn = None
neo4j_driver = None


def connect_mongo():
    client = MongoClient(os.getenv("MONGO_URI"))
    return client[os.getenv("MONGO_DB")]          

def connect_mysql():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
    )

def connect_neo4j():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

def setup_mysql(conn):
   
    cur = conn.cursor()
    for r in RIDERS:
        cur.execute("""
            INSERT INTO riders (number, name, team, maker)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE name=VALUES(name), team=VALUES(team), maker=VALUES(maker)
        """, (r["number"], r["name"], r["team"], r["maker"]))
    conn.commit()
    print("MySQL ready (riders seeded).")

def setup_neo4j(driver):
    with driver.session() as session:
        for r in RIDERS:
            session.run("""
                MERGE (rd:Rider {number: $number})
                  SET rd.name = $name
                MERGE (t:Team  {name: $team})
                MERGE (m:Maker {name: $maker})
                MERGE (rd)-[:RIDES_FOR]->(t)
                MERGE (t)-[:USES]->(m)
            """, number=r["number"], name=r["name"], team=r["team"], maker=r["maker"])
    print("Neo4j ready (rider/team/maker structure).")



def save_telemetry(data):
    
    data["_id"] = f"{data['rider']}-{data['lap']}-{data['sector']}-{data['i']}"
    mongo_db.telemetry.insert_one(data)          

def save_lap(data):
    s = data["sectors"]                          
    cur = mysql_conn.cursor()
    cur.execute("""
        INSERT INTO laps (rider_number, lap, lap_time, sector1, sector2, sector3)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (data["rider"], data["lap"], data["lap_time"], s[0], s[1], s[2]))
    mysql_conn.commit()

def save_overtake(data):
    with neo4j_driver.session() as session:
        session.run("""
            MATCH (a:Rider {name: $overtaker}), (b:Rider {name: $overtaken})
            CREATE (a)-[:OVERTOOK {lap: $lap}]->(b)
        """, overtaker=data["overtaker"], overtaken=data["overtaken"], lap=data["lap"])

def save_draft(data):
    with neo4j_driver.session() as session:
        session.run("""
            MATCH (f:Rider {name: $follower}), (l:Rider {name: $leader})
            CREATE (f)-[:DRAFTING {lap: $lap, gap: $gap}]->(l)
        """, follower=data["follower"], leader=data["leader"], lap=data["lap"], gap=data["gap"])


telemetry_count = 0                              

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to broker (code {reason_code}). Listening...\n")
    client.subscribe([("telemetry/#", 0), ("lap/#", 0), ("event/overtake", 0), ("event/draft", 0)])

def on_message(client, userdata, msg):
    global telemetry_count
    try:
        data = json.loads(msg.payload)            
        topic = msg.topic

        if topic.startswith("telemetry/"):
            save_telemetry(data)
            telemetry_count += 1
            if telemetry_count % 20 == 0:          
                print(f"  MongoDB  <- {telemetry_count} telemetry readings so far")

        elif topic.startswith("lap/"):
            save_lap(data)
            print(f"  MySQL    <- lap {data['lap']} for #{data['rider']} ({data['lap_time']}s)")

        elif topic == "event/overtake":
            save_overtake(data)
            print(f"  Neo4j    <- OVERTAKE: {data['overtaker']} passed {data['overtaken']}")

        elif topic == "event/draft":
            save_draft(data)
            print(f"  Neo4j    <- DRAFT: {data['follower']} drafting {data['leader']}")

    except Exception as e:
        print(f"  ! could not handle message on {msg.topic}: {e}")

def main():
    global mongo_db, mysql_conn, neo4j_driver

    print("Connecting to databases...")
    mongo_db     = connect_mongo()
    mysql_conn   = connect_mysql()
    neo4j_driver = connect_neo4j()

    setup_mysql(mysql_conn)
    setup_neo4j(neo4j_driver)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    client.loop_forever()                          


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCatcher stopped.")
