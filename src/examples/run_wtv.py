# --- HACK: Allow the example to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

import os
import sys
import datetime

from openmovement.load import MultiData
from openmovement.process import calc_wtv

def run_wtv(source_file):
    ext = '.cwtv.csv'

    with MultiData(source_file, verbose=True, include_gyro=False, include_temperature=False) as data:
        samples = data.get_temperature_values()
    
    wtv_calc = calc_wtv.calculate_wtv(samples)
    
    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        writer.write("Time,Wear time (30 mins)\n")
        for time, wtv in wtv_calc:
            time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ')[0:19]
            line = time_string + "," + str(int(wtv))
            writer.write(line + "\n")

            print(line)


if __name__ == "__main__":
    source_files = None
    #source_files = ['../_local/data/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv']
    #source_files = ['../_local/data/sample.csv']
    source_files = ['../_local/data/sample.cwa']
    #source_files = ['../_local/data/mixed_wear.csv']
    #source_files = ['../_local/data/mixed_wear.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run_wtv(file)
