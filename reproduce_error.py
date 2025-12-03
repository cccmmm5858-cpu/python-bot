
import pandas as pd
import datetime
from transits import calc_transit_to_transit, get_aspect_details
from config import ASPECTS

print("Checking ASPECTS structure:")
for item in ASPECTS:
    print(f"  Item length: {len(item)}")

print("\nChecking get_aspect_details return:")
ret = get_aspect_details(0)
print(f"  Returns length: {len(ret)}")

print("\nRunning calc_transit_to_transit...")
# Create a dummy dataframe
data = {
    "Datetime": [datetime.datetime.now()],
    "Sun Lng": [0],
    "Moon Lng": [120],
    "Mercury Lng": [90],
    "Venus Lng": [180],
    "Mars Lng": [60],
    "Jupiter Lng": [0],
    "Saturn Lng": [0],
    "Uranus Lng": [0],
    "Neptune Lng": [0],
    "Pluto Lng": [0],
    "Lunar North Node (True) Lng": [0],
    "Lunar South Node (True) Lng": [0]
}
df = pd.DataFrame(data)

try:
    results = calc_transit_to_transit(df, datetime.datetime.now())
    print(f"Success! Got {len(results)} results.")
except Exception as e:
    print(f"CRASHED: {e}")
