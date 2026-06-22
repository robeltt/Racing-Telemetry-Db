import time
import json
import random
import paho.mqtt.client as mqtt         

from riders import RIDERS, TRACK         

BROKER = "localhost"      
PORT   = 1883             

LAPS               = 5    
SECTORS            = 3   
SAMPLES_PER_SECTOR = 3    
TICK               = 0.4 
DRAFT_GAP          = 1.0  

RIDER_BY_NUMBER = {r["number"]: r for r in RIDERS}

def publish(client, topic, payload):
    client.publish(topic, json.dumps(payload))

def track_position(progress):
    n = len(TRACK)
    point = progress * n             
    i = int(point) % n              
    j = (i + 1) % n                  
    frac = point - int(point)      
    lng = TRACK[i][0] + frac * (TRACK[j][0] - TRACK[i][0])  
    lat = TRACK[i][1] + frac * (TRACK[j][1] - TRACK[i][1])  
    return [round(lng, 6), round(lat, 6)]


def emit_telemetry(client, rider, lap, sector):
    num = rider["number"]
    for i in range(SAMPLES_PER_SECTOR):
        
        progress = ((sector - 1) + (i / SAMPLES_PER_SECTOR)) / SECTORS
        gps = track_position(progress)               

        
        braking = random.random() < 0.4
        if braking:
            speed, throttle, brake, lean = random.randint(90, 160), 0, random.randint(70, 100), random.randint(8, 25)
        else:
            speed, throttle, brake, lean = random.randint(200, 300), random.randint(70, 100), 0, random.randint(30, 55)

        reading = {
            "rider": num,
            "name": rider["name"],
            "lap": lap,
            "sector": sector,
            "i": i,                                       
            "pos": {"type": "Point", "coordinates": gps},  
            "speed": speed,                              
            "throttle": throttle,                         
            "brake": brake,                              
            "lean": lean,                                
            "gear": random.randint(2, 6),                 
            "tyre_temp": round(random.uniform(86, 98), 1),
            "engine_temp": round(random.uniform(95, 108), 1),
            "fuel": round(max(0, 100 - lap * 3 - i), 1),  
            "t": time.strftime("%H:%M:%S"),
        }
        publish(client, f"telemetry/{num}", reading)
        time.sleep(TICK)



def publish_lap(client, rider, lap, lap_time, sector_times):
    num = rider["number"]
    message = {
        "rider": num,
        "name": rider["name"],
        "lap": lap,
        "lap_time": round(lap_time, 3),
        "sectors": [round(s, 3) for s in sector_times],
    }
    publish(client, f"lap/{num}", message)
    print(f"  lap {lap}  #{num:>2} {rider['name']:<6} {lap_time:6.2f}s")



def detect_overtakes(client, prev_order, new_order, lap):
    pos_prev = {num: i for i, num in enumerate(prev_order)}   
    pos_new  = {num: i for i, num in enumerate(new_order)}   
    for a in new_order:
        for b in new_order:
            if a == b:
                continue
            if pos_prev[a] > pos_prev[b] and pos_new[a] < pos_new[b]:
                event = {
                    "lap": lap,
                    "overtaker": RIDER_BY_NUMBER[a]["name"],
                    "overtaken": RIDER_BY_NUMBER[b]["name"],
                }
                publish(client, "event/overtake", event)
                print(f"        OVERTAKE: {event['overtaker']} passed {event['overtaken']}")

def detect_drafts(client, order, total_time, lap):
    for k in range(len(order) - 1):
        leader   = order[k]
        follower = order[k + 1]
        gap = total_time[follower] - total_time[leader]
        if gap <= DRAFT_GAP:
            event = {
                "lap": lap,
                "follower": RIDER_BY_NUMBER[follower]["name"],
                "leader":   RIDER_BY_NUMBER[leader]["name"],
                "gap": round(gap, 3),
            }
            publish(client, "event/draft", event)
            print(f"        DRAFT: {event['follower']} is drafting {event['leader']} (+{event['gap']}s)")



def main():
  
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()                       
    print(f"Connected to broker at {BROKER}:{PORT}. Lights out!\n")

    total_time = {r["number"]: 0.0 for r in RIDERS}      
    prev_order = [r["number"] for r in RIDERS]           

    lap = 1
    while LAPS == 0 or lap <= LAPS:
        print(f"--- Lap {lap} ---")
        for rider in RIDERS:
            sector_times = []
            for sector in range(1, SECTORS + 1):
                st = (rider["pace"] / SECTORS) * random.uniform(0.97, 1.03)
                sector_times.append(st)
                emit_telemetry(client, rider, lap, sector)   
            lap_time = sum(sector_times)
            total_time[rider["number"]] += lap_time
            publish_lap(client, rider, lap, lap_time, sector_times)

        
        new_order = sorted(total_time, key=lambda n: total_time[n])
        detect_overtakes(client, prev_order, new_order, lap)
        detect_drafts(client, new_order, total_time, lap)
        prev_order = new_order
        lap += 1
        print()

    client.loop_stop()
    client.disconnect()
    print("Race finished. All messages sent.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:               
        print("\nStopped by user.")
