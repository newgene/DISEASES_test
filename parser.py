import os
import csv
import json
from itertools import groupby
from operator import itemgetter
from biothings_client import get_client


def batch_query_mondo_from_doid(doid_list):
    """ convert a list of doids to a list of mondo ids

    Keyword arguments:
    doid_list: a list of doids
    """
    mapping_dict = {}
    print('total doids: {}'.format(len(doid_list)))
    id_list = list(set(doid_list))
    print('unique doids: {}'.format(len(id_list)))
    # initiate the mydisease.info python client
    client = get_client('disease')
    # the batch query can only handle 1000 ids at most a time
    for i in range(0, len(id_list), 1000):
        if i + 1000 <= len(id_list):
            batch = id_list[i: i+1000]
        else:
            batch = id_list[i:]
        params = ','.join(batch)
        res = client.querymany(params, scopes="mondo.xrefs.doid", fields="_id")
        for _doc in res:
            if '_id' not in _doc:
                print('can not convert', _doc)
            mapping_dict[_doc['query']] = _doc['_id'] if '_id' in _doc else _doc["query"]
    return mapping_dict

def load_tm_data(file_path):
    """ load data from text mining file

    Keyword arguments:
    file_path -- the file path of the text mining file
    """
    json_docs = []
    with open(file_path) as csvfile:
        fieldnames = ['ensembl', 'symbol', 'doid', 'name', 'zscore', 'confidence', 'url']
        reader = csv.DictReader(csvfile, fieldnames, delimiter='\t')
        for row in reader:
            row.pop('url')
            row.pop('ensembl')
            # convert string to float
            row['zscore'] = float(row['zscore'])
            row['confidence'] = float(row['confidence'])
            row['category'] = 'textmining'
            json_docs.append(dict(row))
    return json_docs

def load_ep_kn_data(file_path, category):
    """ load data from the experiments or knowledge file

    note: the experiments file and the knowledge file share the same column names

    Keyword arguments:
    file_path -- the file path of the experiments or knowledge file
    category -- the category of the file, should be either experiments or knowledge
    """
    json_docs = []
    with open(file_path) as csvfile:
        fieldnames = ['ensembl', 'symbol', 'doid', 'name', 'source', 'evidence', 'confidence']
        reader = csv.DictReader(csvfile, fieldnames, delimiter='\t')
        for row in reader:
            row.pop('ensembl')
            # convert string to float
            row['confidence'] = float(row['confidence'])
            row['category'] = category
            json_docs.append(dict(row))
    return json_docs



def load_data(data_folder):
    """ main data load function

    Keyword arguments:
    data_folder -- folder storing downloaded files
    """
    # path for the text mining file
    tm_path = os.path.join(data_folder, "human_disease_textmining_filtered.tsv")
    # path for the knowledge file
    kn_path = os.path.join(data_folder, "human_disease_knowledge_filtered.tsv")
    # path for the experiments file
    ep_path = os.path.join(data_folder, "human_disease_experiments_filtered.tsv")
    json_docs = load_tm_data(tm_path) + load_ep_kn_data(kn_path, 'knowledge') + load_ep_kn_data(ep_path, 'experiments')
    json_docs = sorted(json_docs, key=itemgetter('doid'))
    doids = [_doc['doid'] for _doc in json_docs if _doc['doid'].startswith('DOID:')]
    mapping = batch_query_mondo_from_doid(doids)
    for key, group in groupby(json_docs, key=itemgetter('doid')):
        res = {
                "DISEASES": {
                    "associatedWith": []
                }
            }
        merged_doc = []
        for _doc in group:
            if key.startswith("DOID:"):
                res["DISEASES"]['doid'] = key
                res["_id"] = mapping[key]
            elif key.startswith("AmyCo:"):
                res["DISEASES"]["amyco"] = res["_id"] = key
            else:
                print(key)
                continue
            _doc.pop("doid")
            res["DISEASES"]["name"] = _doc.pop("name")
            merged_doc.append(_doc)
        res['DISEASES']['associatedWith'] = merged_doc
        yield res