#!/usr/bin/env python

# Script that parses legislators-historical.yaml from
# unitedstates/congress-legislators and extracts now-defunct districts from
# that document.

import requests
import yaml
import csv
import os
import re
import pickle as pickle
import os.path
import hashlib
from us import states  # you'll need to run `pip install us` for this one

SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
HISTORIC_LEGISLATOR_FILE = os.path.join(
    SCRIPT_DIRECTORY,
    '../../cache/legislators-historical.yaml')


def yaml_load(path, use_cache=True):
    # From unitedstates/congress-legislators
    h = hashlib.sha1(open(path, 'rb').read()).hexdigest()
    if use_cache and os.path.exists(path + ".pickle"):

        try:
            store = pickle.load(open(path + ".pickle", 'rb'))
            if store["hash"] == h:
                return store["data"]
        except EOFError:
            pass  # bad .pickle file, pretend it doesn't exist

    # No cached pickled data exists, so load the YAML file.
    print('Loading yaml from scratch. This might take a while...')
    data = yaml.load(open(path))

    # Store in a pickled file for fast access later.
    pickle.dump({"hash": h, "data": data}, open(path+".pickle", "wb"))

    return data


def ordinalize(num):
    # via SO
    suffixes = {1: 'st', 2: 'nd', 3: 'rd'}
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        suffix = suffixes.get(num % 10, 'th')
    return str(num) + suffix


def parse_division_id(division_id):
    if re.search("cd\:(\d+)", division_id):
        district = int(re.search("cd\:(\d+)", division_id).group(1))
    else:
        district = 0
    if re.search("(state|territory):([a-zA-Z]{2})", division_id):
        state = re.search(
            "(state|territory):([a-zA-Z]{2})",
            division_id).group(2)
    else:
        return False
    return (state, district)


def make_division_id(state, district):
    return "ocd-division/country:us/state:{state}/cd:{district}".format(
        state=state,
        district=district)


def make_division_name(state, district):
    return "{state}'s {district} congressional district".format(
        state=states.lookup(state).name,
        district=ordinalize(district))


def make_row(state, district):
    division_id = make_division_id(state, district)
    name = make_division_name(state, district)
    return [division_id, name]


def download_historic_legislators():
    historic_legislators_url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/master/legislators-historical.yaml"
    raw_historic_legislators = requests.get(historic_legislators_url).text
    f = open(
        os.path.join(
            SCRIPT_DIRECTORY,
            "../../cache/legislators-historical.yaml"),
        'w')
    f.write(raw_historic_legislators)
    f.close()


def extract_historical_districts():
    historic_legislator_list = yaml_load(
        os.path.join(
            SCRIPT_DIRECTORY,
            '../../cache/legislators-historical.yaml'))

    historical_districts = set()
    for leg in historic_legislator_list:
        for term in leg['terms']:
            if 'district' in term:
                district_tuple = (term['state'].lower(), term['district'])
                # (value of -1 specifies unknown district)
                if (term['district'] == -1):
                    print("Skipping district {0}".format(district_tuple))
                    continue
                historical_districts.add(district_tuple)
    return historical_districts


def extract_existing_districts():
    congressional_district_id_file = os.path.join(
        SCRIPT_DIRECTORY,
        '../../identifiers/country-us/census_autogenerated/us_congressional_districts.csv')

    existing_districts = set()
    with open(congressional_district_id_file, 'rt') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # skip first line
        for row in reader:
            existing_districts.add(parse_division_id(row[0]))
    return existing_districts


def extract_at_large_districts():
    state_division_id_file = os.path.join(
        SCRIPT_DIRECTORY,
        '../../identifiers/country-us/states.csv')
    territory_division_id_file = os.path.join(
        SCRIPT_DIRECTORY,
        '../../identifiers/country-us/us_territories.csv')

    at_large_districts = set()
    for f in [state_division_id_file, territory_division_id_file]:
        with open(f, 'rt') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                at_large_districts.add(parse_division_id(row[0]))
    at_large_districts.add(('dc', 0))  # add dc; a weird exception
    return at_large_districts


def write_missing_districts(missing_districts):
    new_file_path = os.path.join(
        SCRIPT_DIRECTORY,
        '../../identifiers/country-us/historical/unitedstates_legislators_autogenerated/historical_congressional_districts.csv')

    print(
        "Writing {number} missing districts".format(
            number=len(
                missing_districts)))
    with open(new_file_path, 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "name"])
        for district in missing_districts:
            writer.writerow(make_row(state=district[0], district=district[1]))


if __name__ == "__main__":
    import pdb; pdb.set_trace();
    # Grab historic legislators from congress-legislators
    download_historic_legislators()

    # Extract districts from various sources
    historical_districts = extract_historical_districts()
    existing_districts = extract_existing_districts()
    at_large_districts = extract_at_large_districts()
    existing_districts = existing_districts.union(at_large_districts)

    # Reconcile and write out missing districts
    missing_districts = historical_districts.difference(existing_districts)
    write_missing_districts(missing_districts)
