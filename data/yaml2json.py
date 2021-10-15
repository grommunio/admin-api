#!/usr/bin/env python3

import sys
if len(sys.argv) != 3:
    print("Usage: "+sys.argv[0]+" <input file> <output file>")
    sys.exit(1)

try:
    import json
    import yaml
    with open(sys.argv[1]) as fin, open(sys.argv[2], "w") as fout:
        json.dump(yaml.load(fin, yaml.SafeLoader), fout, separators=(",", ":"))
except BaseException as err:
    print("Failed to convert: "+" - ".join(str(arg) for arg in err.args))
    sys.exit(2)
