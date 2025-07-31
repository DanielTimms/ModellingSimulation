import simpy
import random
import matplotlib.pyplot as plt

RANDOM_SEED = 42
SIM_TIME = 720  # Simulate 12 hours (7am to 7pm)

# Station capacity
STATION_CAPACITY = {
    'Fuel_Pump_Car': 12,         # shared pumps
    'Fuel_Pump_Bike': 2,         # bike-only pumps
    'Fuel_Pump_Trailer': 1,
    'Air_Pump': 2,
    'Staff_Counter': 2,
    'Parking_Space': 20
}

# Interarrival times (mins) per hour per vehicle type
INTERARRIVAL = {
    'Car': [2] + [1]*11,
    'Trailer': [20, 15, 30, 60, 30, 30, 30, 0, 60, 30, 20, 30],
    'Motorcycle': [6, 5, 4, 3, 3, 3, 3, 3, 3, 3, 3, 4]
}

# Average stop durations (mins)
STOP_DURATION = {
    'Car': 8,
    'Trailer': 25,
    'Motorcycle': 5
}

# Service usage probabilities
SERVICE_PROBS = {
    'Car': {
        'Fueling': 0.93, 'Air_Pump': 0.31, 'Windshield': 0.28,
        'Toilet': 0.17, 'Surau': 0.10, 'Shop': 0.45
    },
    'Trailer': {
        'Fueling': 1.00, 'Air_Pump': 0.00, 'Windshield': 0.00,
        'Toilet': 1.00, 'Surau': 0.25, 'Shop': 0.75
    },
    'Motorcycle': {
        'Fueling': 0.93, 'Air_Pump': 0.13, 'Windshield': 0.00,
        'Toilet': 0.17, 'Surau': 0.07, 'Shop': 0.17
    }
}

# Resources
class PetrolStation:
    def __init__(self, env):
        self.fuel_pump_car = simpy.Resource(env, capacity=STATION_CAPACITY['Fuel_Pump_Car'])
        self.fuel_pump_bike = simpy.Resource(env, capacity=STATION_CAPACITY['Fuel_Pump_Bike'])
        self.fuel_pump_trailer = simpy.Resource(env, capacity=STATION_CAPACITY['Fuel_Pump_Trailer'])
        self.air_pump = simpy.Resource(env, capacity=STATION_CAPACITY['Air_Pump'])
        self.counter = simpy.Resource(env, capacity=STATION_CAPACITY['Staff_Counter'])

# Counters
usage_counts = {
    'Car': {k: 0 for k in SERVICE_PROBS['Car'].keys()},
    'Trailer': {k: 0 for k in SERVICE_PROBS['Trailer'].keys()},
    'Motorcycle': {k: 0 for k in SERVICE_PROBS['Motorcycle'].keys()}
}

vehicle_counts = {'Car': 0, 'Trailer': 0, 'Motorcycle': 0}
fuel_success = {'Car': 0, 'Motorcycle': 0, 'Trailer': 0}
fuel_reject = {'Car': 0, 'Motorcycle': 0, 'Trailer': 0}

def vehicle(env, name, station, vehicle_type):
    arrive_time = env.now
    vehicle_counts[vehicle_type] += 1

    if random.random() < SERVICE_PROBS[vehicle_type]['Fueling']:
        if vehicle_type == 'Motorcycle':
            with station.fuel_pump_bike.request() as req_bike:
                result = yield req_bike | env.timeout(5)
                if req_bike in result:
                    yield env.timeout(4)
                    fuel_success[vehicle_type] += 1
                else:
                    with station.fuel_pump_car.request() as req_car:
                        result = yield req_car | env.timeout(5)
                        if req_car in result:
                            yield env.timeout(4)
                            fuel_success[vehicle_type] += 1
                        else:
                            fuel_reject[vehicle_type] += 1
                            return
        elif vehicle_type == 'Trailer':
            with station.fuel_pump_trailer.request() as req:
                result = yield req | env.timeout(5)
                if req in result:
                    yield env.timeout(4)
                    fuel_success[vehicle_type] += 1
                else:
                    fuel_reject[vehicle_type] += 1
                    return
        else:
            with station.fuel_pump_car.request() as req:
                result = yield req | env.timeout(5)
                if req in result:
                    yield env.timeout(4)
                    fuel_success[vehicle_type] += 1
                else:
                    fuel_reject[vehicle_type] += 1
                    return
        usage_counts[vehicle_type]['Fueling'] += 1

    if vehicle_type != 'Trailer' and random.random() < SERVICE_PROBS[vehicle_type]['Air_Pump']:
        with station.air_pump.request() as req:
            yield req
            yield env.timeout(1)
            usage_counts[vehicle_type]['Air_Pump'] += 1

    if vehicle_type != 'Trailer' and random.random() < SERVICE_PROBS[vehicle_type]['Windshield']:
        yield env.timeout(0.5)
        usage_counts[vehicle_type]['Windshield'] += 1

    if random.random() < SERVICE_PROBS[vehicle_type]['Toilet']:
        yield env.timeout(1)
        usage_counts[vehicle_type]['Toilet'] += 1

    if random.random() < SERVICE_PROBS[vehicle_type]['Surau']:
        yield env.timeout(2)
        usage_counts[vehicle_type]['Surau'] += 1

    if random.random() < SERVICE_PROBS[vehicle_type]['Shop']:
        with station.counter.request() as req:
            yield req
            yield env.timeout(3)
            usage_counts[vehicle_type]['Shop'] += 1

    yield env.timeout(STOP_DURATION[vehicle_type])

def vehicle_arrivals(env, station):
    id_counter = {'Car': 1, 'Trailer': 1, 'Motorcycle': 1}
    while True:
        current_hour = int(env.now // 60)
        if current_hour >= len(INTERARRIVAL['Car']):
            break

        for vt in ['Car', 'Trailer', 'Motorcycle']:
            iat = INTERARRIVAL[vt][current_hour]
            if iat > 0 and random.random() < 1 / iat:
                name = f"{vt}_{id_counter[vt]}"
                env.process(vehicle(env, name, station, vt))
                id_counter[vt] += 1

        yield env.timeout(1)

def run_sim():
    random.seed(RANDOM_SEED)
    env = simpy.Environment()
    station = PetrolStation(env)
    env.process(vehicle_arrivals(env, station))
    env.run(until=SIM_TIME)

    print("\n--- Final Vehicle Counts ---")
    for vt in vehicle_counts:
        print(f"{vt}s: {vehicle_counts[vt]}")

    print("\n--- Service Usage Summary (By Vehicle Type) ---")
    for vt in usage_counts:
        print(f"\n{vt}s:")
        for service, count in usage_counts[vt].items():
            print(f"  {service}: {count}")

    print("\n--- Fueling Success vs Rejected ---")
    for vt in fuel_success:
        print(f"{vt}s - Success: {fuel_success[vt]}, Rejected: {fuel_reject[vt]}")

    plt.figure(figsize=(6, 4))
    bars = plt.bar(vehicle_counts.keys(), vehicle_counts.values(), color='skyblue')
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height, str(height), ha='center', va='bottom')
    plt.title('Total Vehicles Processed During Simulation')
    plt.xlabel('Vehicle Type')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.show()

    services = list(SERVICE_PROBS['Car'].keys())
    vehicle_types = ['Car', 'Trailer', 'Motorcycle']
    bottom = [0] * len(vehicle_types)

    plt.figure(figsize=(10, 6))
    for service in services:
        values = [usage_counts[vt][service] for vt in vehicle_types]
        bars = plt.bar(vehicle_types, values, bottom=bottom, label=service)
        for i, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., bottom[i] + height/2., str(height), ha='center', va='center', fontsize=8, color='white')
        bottom = [bottom[i] + values[i] for i in range(len(bottom))]

    plt.title('Service Usage by Vehicle Type (Stacked)')
    plt.xlabel('Vehicle Type')
    plt.ylabel('Total Service Usage')
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Fueling Success vs Rejected Bar Chart
    labels = list(fuel_success.keys())
    success_values = [fuel_success[vt] for vt in labels]
    reject_values = [fuel_reject[vt] for vt in labels]

    x = range(len(labels))
    plt.figure(figsize=(8, 5))
    plt.bar(x, success_values, label='Success', color='green')
    plt.bar(x, reject_values, bottom=success_values, label='Rejected', color='red')
    plt.xticks(x, labels)
    plt.ylabel('Vehicle Count')
    plt.title('Fueling Success vs Rejection by Vehicle Type')
    plt.legend()
    plt.tight_layout()
    plt.show()

run_sim()
