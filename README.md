# Racing — A Telemetry System for Motorcycle Racing

![Racing telemetry](image.webp)
a single stream of simulated motorcycle-racing data is published over **MQTT** and
routed, by message type, into the database best suited to it:

- **MySQL** — structured lap and sector timing (with a trigger, a view, and a stored procedure)
- **MongoDB** — the raw high-frequency telemetry firehose (with geospatial and aggregation queries)
- **Neo4j** — the overtaking and drafting networks between riders (graph queries)

A **Streamlit** dashboard reads from all three databases at once to present the results.
Everything runs in **Docker**.

```
Simulator  →  MQTT broker (Mosquitto)  →  Subscriber  →  MySQL · MongoDB · Neo4j  →  Dashboard
```

---

## Requirements

- [Docker](https://www.docker.com/) (Docker Desktop)
- Python 3.10+

---

## How to run

All commands are run from the project folder.

### 1. Install the Python requirements

```bash
pip install -r requirements.txt
```

### 2. Start the databases and broker (Docker)

```bash
docker compose up -d
```

This starts four containers: Mosquitto (MQTT), MySQL, MongoDB and Neo4j.
Give them a few seconds to finish starting. You can check them with `docker ps`.

### 3. Load the MySQL schema

This creates the tables, the trigger, the view and the stored procedure.
preferebly Run it once in MySQL Workbench:


### 4. Start the subscriber (the router)

In one terminal, start the program that listens to the broker and writes to the databases:

```bash
python subscriber.py
```

Wait until it prints that it is connected and listening.

### 5. Run the simulator

In a second terminal, start the race:

```bash
python simulator.py
```

The simulator publishes telemetry, lap and event messages; the subscriber files them
into MongoDB, MySQL and Neo4j.

### 6. (Optional) Open the dashboard

```bash
streamlit run dashboard.py
```

Then open the link it prints (usually http://localhost:8501).

---

## Services and credentials

| Service   | URL / Port              | Credentials              |
|-----------|-------------------------|--------------------------|
| MQTT      | `localhost:1883`        | anonymous                |
| MySQL     | `localhost:3306`        | `root` / `racing123`     |
| MongoDB   | `localhost:27017`       | none (local dev)         |
| Neo4j     | http://localhost:7474   | `neo4j` / `racing123`    |

Connection settings are kept in a `.env` file (excluded from version control).

---

## Stopping

```bash
docker compose down       # stop the containers (data is kept)
docker compose down -v    # stop and wipe all database data
```

> After `down -v`, re-run step 3 (load the schema) before starting the subscriber again.

---

## Project structure

| File                 | Purpose                                                        |
|----------------------|----------------------------------------------------------------|
| `docker-compose.yml` | Defines the four services (Mosquitto, MySQL, MongoDB, Neo4j)    |
| `schema.sql`         | MySQL tables, trigger, view and stored procedure               |
| `riders.py`          | Shared rider and track data (used by simulator and subscriber) |
| `simulator.py`       | Generates the race and publishes messages over MQTT            |
| `subscriber.py`      | Listens to the broker and routes each message to a database    |
| `dashboard.py`       | Streamlit dashboard reading from all three databases           |
| `requirements.txt`   | Python dependencies                                            |
