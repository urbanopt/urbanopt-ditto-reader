import json
import sys
from urbanopt_ditto_reader import UrbanoptDittoReader

# Convert inputs and run opendss

config_data = {}

# get file argument containing config
if len(sys.argv) == 2:
    config_file = sys.argv[1]
    data = open(config_file)
    config_data = json.load(data)
    data.close()
else:
    print("No config argument passed.  Using default configs")

c = UrbanoptDittoReader(config_data)
c.run()
