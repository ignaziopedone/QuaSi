import yaml

pref_file = open("./NetTopologyTest.yaml", 'r')
prefs = yaml.safe_load(pref_file)

print(prefs["spec"]["adjacency"])