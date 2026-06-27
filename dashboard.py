import os
import pandas as pd
import altair as alt
import streamlit as st
from dotenv import load_dotenv
import mysql.connector
from pymongo import MongoClient
from neo4j import GraphDatabase

from riders import RIDERS

load_dotenv()

RIDER_COLORS = {r["name"]: r["color"] for r in RIDERS}


st.set_page_config(page_title="Racing Dashboard", layout="wide")
st.title("🏁 Racing — Live Telemetry Dashboard")
st.caption("One system, three databases:  MySQL · MongoDB · Neo4j")
col_l, col_mid, col_r = st.columns([1, 2, 1])
with col_mid:
    st.image("image.webp", use_container_width=True)

def get_mysql():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"), port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"), password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
    )

def get_mongo():
    return MongoClient(os.getenv("MONGO_URI"))[os.getenv("MONGO_DB")]

def get_neo4j():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

def sql_df(conn, query):
    cur = conn.cursor(dictionary=True)
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows)

def cypher_df(driver, query):
    with driver.session() as session:
        return pd.DataFrame([record.data() for record in session.run(query)])

def colored_bar(df, value_col, y_title):
    domain = list(RIDER_COLORS.keys())
    colors = [RIDER_COLORS[name] for name in domain]
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("rider:N", sort="-y", title=None),
            y=alt.Y(f"{value_col}:Q", title=y_title),
            color=alt.Color("rider:N",
                            scale=alt.Scale(domain=domain, range=colors),
                            legend=None),
            tooltip=["rider", value_col],
        )
    )
    st.altair_chart(chart, use_container_width=True)


st.header("🗄️ MySQL — timing & standings")
try:
    conn = get_mysql()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Leaderboard (view)")
        st.dataframe(sql_df(conn, "SELECT * FROM leaderboard"), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Personal bests (written by the trigger)")
        pbs = sql_df(conn, """
            SELECT r.number,r.name, pb.lap, pb.lap_time, pb.logged_at
            FROM personal_best_log pb
            JOIN riders r ON r.number = pb.rider_number
            ORDER BY pb.logged_at
        """)
        st.dataframe(pbs, use_container_width=True, hide_index=True)



    st.subheader("Rider report")
    riders_list = sql_df(conn, "SELECT number, name FROM riders ORDER BY number")
    if not riders_list.empty:
        choice = st.selectbox(
            "Pick a rider",
            riders_list["number"],
            format_func=lambda n: riders_list.set_index("number").loc[n, "name"],
        )
        cur = conn.cursor(dictionary=True)
        cur.callproc("rider_report", [int(choice)])    
        report = []
        for result in cur.stored_results():
            report = result.fetchall()
        cur.close()
        st.dataframe(pd.DataFrame(report), use_container_width=True, hide_index=True)
    conn.close()
except Exception as e:
    st.error(f"MySQL not available: {e}")


st.header("🍃 MongoDB — telemetry firehose")
try:
    db = get_mongo()
    st.metric("Total telemetry readings", db.telemetry.count_documents({}))

    st.subheader("Average speed per rider")
    speed = list(db.telemetry.aggregate([
        {"$group": {"_id": "$name",
                    "top_speed": {"$max": "$speed"},
                    "avg_speed": {"$avg": "$speed"}}},
        {"$sort": {"avg_speed": -1}},
    ]))
    speed_df = pd.DataFrame(speed).rename(columns={"_id": "rider"})
    if not speed_df.empty:
        speed_df["avg_speed"] = speed_df["avg_speed"].round(1)
    st.dataframe(speed_df, use_container_width=True, hide_index=True)
    if not speed_df.empty:
        colored_bar(speed_df, "avg_speed", "Avg speed (km/h)")
except Exception as e:
    st.error(f"MongoDB not available: {e}")


st.header("🕸️ Neo4j — overtaking & drafting network")
try:
    driver = get_neo4j()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Most aggressive (overtakes)")
        agg = cypher_df(driver, """
            MATCH (r:Rider)-[o:OVERTOOK]->()
            RETURN r.name AS rider, count(o) AS overtakes
            ORDER BY overtakes DESC
        """)
        st.dataframe(agg, use_container_width=True, hide_index=True)
        if not agg.empty:
            colored_bar(agg, "overtakes", "Overtakes")

    with col2:
        st.subheader("Longest draft trains (lap 1)")
        trains = cypher_df(driver, """
            MATCH path = (tail:Rider)-[:DRAFTING*]->(head:Rider)
            WHERE all(rel IN relationships(path) WHERE rel.lap = 1)
            RETURN [n IN nodes(path) | n.name] AS train, length(path) AS length
            ORDER BY length DESC
            LIMIT 5
        """)
        if not trains.empty:
            trains["train"] = trains["train"].apply(lambda names: " → ".join(names))
        st.dataframe(trains, use_container_width=True, hide_index=True)
    driver.close()
except Exception as e:
    st.error(f"Neo4j not available: {e}")

