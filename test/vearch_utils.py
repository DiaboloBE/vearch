#
# Copyright 2019 The Vearch Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

# -*- coding: UTF-8 -*-

import requests
import os
import shutil
import tarfile
from ftplib import FTP
from urllib.parse import urlparse
import socket
import numpy as np
import json
import time
import random
from multiprocessing import Pool as ThreadPool


ip = "127.0.0.1"
ip_master = ip + ":8817"
ip_router = ip + ":9001"
router_url = "http://" + ip_router
db_name = "ts_db"
space_name = "ts_space"


__description__ = """ test utils for vearch """


def get_ftp_ip(url):
    parsed_url = urlparse(url)
    ftp_host = parsed_url.hostname
    ip_address = socket.gethostbyname(ftp_host)

    return ip_address


def ivecs_read(fname):
    a = np.fromfile(fname, dtype="int32")
    d = a[0]
    return a.reshape(-1, d + 1)[:, 1:].copy()


def fvecs_read(fname):
    return ivecs_read(fname).view("float32")


def download_sift(logger, host, dirname, filename):
    if os.path.isfile(filename):
        logger.debug("%s exists, no need to download" % (filename))
        return True
    ftp = FTP(host)
    ftp.login()
    ftp.set_pasv(True)
    ftp.cwd(dirname)

    with open(filename, "wb") as local_file:
        ftp.retrbinary("RETR " + filename, local_file.write)
    ftp.quit()

    if os.path.isfile(filename):
        logger.debug("%s successful download" % (filename))
        return True
    else:
        logger.error("%s download failed" % (filename))
        return False


def untar(fname, dirs):
    t = tarfile.open(fname)
    t.extractall(path=dirs)


def load_sift1M(logger):
    xt = fvecs_read("sift/sift_learn.fvecs")
    xb = fvecs_read("sift/sift_base.fvecs")
    xq = fvecs_read("sift/sift_query.fvecs")
    gt = ivecs_read("sift/sift_groundtruth.ivecs")
    logger.debug("successful load sift1M")
    return xb, xq, xt, gt


def load_sift10K(logger):
    xt = fvecs_read("siftsmall/siftsmall_learn.fvecs")
    xb = fvecs_read("siftsmall/siftsmall_base.fvecs")
    xq = fvecs_read("siftsmall/siftsmall_query.fvecs")
    gt = ivecs_read("siftsmall/siftsmall_groundtruth.ivecs")
    logger.debug("successful load sift10K")
    return xb, xq, xt, gt


def get_sift1M(logger):
    url = "ftp://ftp.irisa.fr"
    dirname = "local/texmex/corpus/"
    filename = "sift.tar.gz"
    host = ftp_ip = get_ftp_ip(url)
    if download_sift(logger, host, dirname, filename) == False:
        return
    untar(filename, "./")
    xb, xq, xt, gt = load_sift1M(logger)
    return xb, xq, xt, gt


def get_sift10K(logger):
    url = "ftp://ftp.irisa.fr"
    dirname = "local/texmex/corpus/"
    filename = "siftsmall.tar.gz"
    host = ftp_ip = get_ftp_ip(url)
    if download_sift(logger, host, dirname, filename) == False:
        return
    untar(filename, "./")
    xb, xq, xt, gt = load_sift10K(logger)
    return xb, xq, xt, gt


def process_add_data(items):
    url = router_url + "/document/upsert"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["documents"] = []
    index = items[0]
    batch_size = items[1]
    features = items[2]
    with_id = items[3]
    full_field = items[4]
    seed = items[5]
    for j in range(batch_size):
        param_dict = {}
        if with_id:
            param_dict["_id"] = str(index * batch_size + j)
        param_dict["field_int"] = (index * batch_size + j) * seed
        param_dict["field_vector"] = {"feature": features[j].tolist()}
        if full_field:
            param_dict["field_long"] = param_dict["field_int"]
            param_dict["field_float"] = float(param_dict["field_int"])
            param_dict["field_double"] = float(param_dict["field_int"])
            param_dict["field_string"] = str(param_dict["field_int"])
        data["documents"].append(param_dict)

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)


def add(total, batch_size, xb, with_id=False, full_field=False, seed=1):
    pool = ThreadPool()
    total_data = []
    for i in range(total):
        total_data.append(
            (
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                with_id,
                full_field,
                seed,
            )
        )
    results = pool.map(process_add_data, total_data)
    pool.close()
    pool.join()


def process_add_embedding_size_data(items):
    url = router_url + "/document/upsert"
    data = {}
    data["documents"] = []

    add_db_name = items[0]
    add_space_name = items[1]
    index = items[2]
    batch_size = items[3]
    embedding_size = items[4]

    data["db_name"] = add_db_name
    data["space_name"] = add_space_name
    for j in range(batch_size):
        param_dict = {}
        param_dict["_id"] = str(index * batch_size + j)
        param_dict["field_int"] = index * batch_size + j
        param_dict["field_vector"] = {"feature": [random.random() for i in range(embedding_size)]}
        param_dict["field_long"] = param_dict["field_int"]
        param_dict["field_float"] = float(param_dict["field_int"])
        param_dict["field_double"] = float(param_dict["field_int"])
        param_dict["field_string"] = str(param_dict["field_int"])
        data["documents"].append(param_dict)

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)


def add_embedding_size(db_name, space_name, total, batch_size, embedding_size):
    pool = ThreadPool()
    total_data = []
    for i in range(total):
        total_data.append(
            (
                db_name,
                space_name,
                i,
                batch_size,
                embedding_size
            )
        )
    results = pool.map(process_add_embedding_size_data, total_data)
    pool.close()
    pool.join()


def process_add_error_data(items):
    url = router_url + "/document/upsert"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["documents"] = []
    index = items[0]
    batch_size = items[1]
    features = items[2]
    logger = items[3]
    wrong_number_value = items[4][0]
    wrong_str_value = items[4][1]
    without_vector = items[4][2]
    wrong_db = items[4][3]
    wrong_space = items[4][4]
    wrong_field = items[4][5]
    empty_documents = items[4][6]
    wrong_index_string_length = items[4][7]
    wrong_string_length = items[4][8]
    wrong_vector_type = items[4][9]
    wrong_vector_feature_length = items[4][10]
    wrong_vector_feature_type = items[4][11]
    mismatch_field_type = items[4][12]
    max_index_str_length = 1025
    max_str_length = 65536

    if wrong_db:
        data["db_name"] = "wrong_db"
    if wrong_space:
        data["space_name"] = "wrong_space"
    for j in range(batch_size):
        param_dict = {}
        param_dict["field_int"] = index * batch_size + j

        if not without_vector:
            if wrong_vector_type:
                param_dict["field_vector"] = features[j].tolist()
            if wrong_vector_feature_length:
                param_dict["field_vector"] = {"feature": features[j].tolist()[:1]}
            if wrong_vector_feature_type:
                param_dict["field_vector"] = {"feature": features[j].tolist()[0]}
            if not wrong_vector_type and not wrong_vector_feature_length and not wrong_vector_feature_type:
                param_dict["field_vector"] = {"feature": features[j].tolist()}

        param_dict["field_string"] = str(param_dict["field_int"])
        if wrong_str_value:
            param_dict["field_string"] = float(param_dict["field_int"])

        if wrong_index_string_length:
            param_dict["field_string"] = "".join(
                ["0" for _ in range(max_index_str_length)]
            )

        if wrong_string_length:
            param_dict["field_string1"] = "".join(["0" for _ in range(max_str_length)])

        if wrong_number_value:
            param_dict["field_long"] = param_dict["field_int"]
            param_dict["field_float"] = "field_float"
            param_dict["field_double"] = "field_double"
        else:
            param_dict["field_long"] = param_dict["field_int"]
            param_dict["field_float"] = float(param_dict["field_int"])
            param_dict["field_double"] = float(param_dict["field_int"])
        if wrong_field:
            param_dict["field_wrong"] = param_dict["field_int"]

        if mismatch_field_type:
            param_dict["field_int"] = {"feature": features[j].tolist()}

        if not empty_documents:
            data["documents"].append(param_dict)

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)

    if not wrong_string_length:
        logger.info(json_str)
    logger.info(rs.json())

    assert rs.status_code != 200


def add_error(total, batch_size, xb, logger, wrong_parameters: list):
    for i in range(total):
        process_add_error_data(
            (
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                logger,
                wrong_parameters,
            )
        )


def process_add_multi_vec_data(items):
    url = router_url + "/document/upsert"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["documents"] = []
    index = items[0]
    batch_size = items[1]
    features = items[2]
    with_id = items[3]
    full_field = items[4]
    seed = items[5]
    for j in range(batch_size):
        param_dict = {}
        if with_id:
            param_dict["_id"] = str(index * batch_size + j)
        param_dict["field_int"] = (index * batch_size + j) * seed
        param_dict["field_vector"] = {"feature": features[j].tolist()}
        param_dict["field_vector1"] = {"feature": features[j].tolist()}
        if full_field:
            param_dict["field_long"] = param_dict["field_int"]
            param_dict["field_float"] = float(param_dict["field_int"])
            param_dict["field_double"] = float(param_dict["field_int"])
            param_dict["field_string"] = str(param_dict["field_int"])
        data["documents"].append(param_dict)

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)


def add_multi_vector(total, batch_size, xb, with_id=False, full_field=False, seed=1):
    pool = ThreadPool()
    total_data = []
    for i in range(total):
        total_data.append(
            (
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                with_id,
                full_field,
                seed,
            )
        )
    results = pool.map(process_add_multi_vec_data, total_data)
    pool.close()
    pool.join()


def prepare_filter(filter, index, batch_size, seed, full_field):
    if full_field:
        # term_filter = {
        #    "term": {
        #        "field_string": [str(i) for i in range(index * batch_size * seed, (index + 1) * batch_size * seed)]
        #    }
        # }
        # filter.append(term_filter)
        range_filter = {
            "range": {
                "field_int": {
                    "gte": (index * batch_size) * seed,
                    "lt": (index + 1) * batch_size * seed,
                },
                "field_long": {
                    "gte": (index * batch_size) * seed,
                    "lt": (index + 1) * batch_size * seed,
                },
                "field_float": {
                    "gt": float(index * batch_size * seed),
                    "lt": float((index + 1) * batch_size * seed),
                },
                "field_double": {
                    "gt": float(index * batch_size * seed),
                    "lt": float((index + 1) * batch_size * seed),
                },
            }
        }
        filter.append(range_filter)
    else:
        range_filter = {
            "range": {
                "field_int": {
                    "gte": (index * batch_size) * seed,
                    "lt": (index + 1) * batch_size * seed,
                }
            }
        }
        filter.append(range_filter)


def prepare_range_filter(filter, index, batch_size):
    range_filter = {
        "range": {
            "field_int": {"gte": index * batch_size, "lte": (index + 1) * batch_size}
        }
    }
    filter.append(range_filter)


def prepare_wrong_range_filter(filter, index, batch_size):
    range_filter = {
        "range": {
            "field_string": [
                str(i) for i in range(index * batch_size, (index + 1) * batch_size)
            ]
        }
    }
    filter.append(range_filter)


def prepare_wrong_range_filter_name(filter, index, batch_size):
    range_filter = {
        "range": {
            "wrong_name": {"gte": index * batch_size, "lte": (index + 1) * batch_size}
        }
    }
    filter.append(range_filter)


def prepare_wrong_index_filter(filter, index, batch_size):
    range_filter = {
        "range": {
            "field_long": {"gte": index * batch_size, "lte": (index + 1) * batch_size}
        }
    }
    filter.append(range_filter)


def prepare_term_filter(filter, index, batch_size):
    term_filter = {
        "term": {
            "field_string": [
                str(i) for i in range(index * batch_size, (index + 1) * batch_size)
            ]
        }
    }
    filter.append(term_filter)


def prepare_wrong_term_filter_name(filter, index, batch_size):
    term_filter = {
        "term": {
            "wrong_name": [
                str(i) for i in range(index * batch_size, (index + 1) * batch_size)
            ]
        }
    }
    filter.append(term_filter)


def prepare_wrong_term_filter(filter, index, batch_size):
    term_filter = {
        "term": {
            "field_int": {"gte": index * batch_size, "lte": (index + 1) * batch_size}
        }
    }
    filter.append(term_filter)


def process_query_error_data(items):
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["query"] = {}
    index = items[0]
    batch_size = items[1]
    features = items[2]
    logger = items[3]
    interface = items[4]
    url = router_url + "/document/" + interface

    (
        wrong_db,
        wrong_space,
        wrong_id,
        wrong_partition,
        wrong_range_filter,
        wrong_term_filter,
        wrong_filter_index,
        wrong_vector,
        wrong_length_document_ids,
        wrong_both_id_and_filter,
        empty_query,
        empty_document_ids,
        empty_filter,
        wrong_range_filter_name,
        wrong_term_filter_name,
        out_of_bounds_ids,
    ) = items[5]

    max_document_ids_length = 501

    if wrong_db:
        data["db_name"] = "wrong_db"
    if wrong_space:
        data["space_name"] = "wrong_space"

    if wrong_partition and interface == "query":
        data["query"]["document_ids"] = ["0"]
        data["query"]["partition_id"] = "1008611"

    if wrong_id:
        data["query"]["document_ids"] = ["wrong_id"]

    if wrong_range_filter:
        data["query"]["filter"] = []
        prepare_wrong_range_filter(data["query"]["filter"], index, batch_size)
        data["size"] = batch_size

    if wrong_term_filter:
        data["query"]["filter"] = []
        prepare_wrong_term_filter(data["query"]["filter"], index, batch_size)
        data["size"] = batch_size

    if wrong_filter_index:
        data["query"]["filter"] = []
        prepare_wrong_index_filter(data["query"]["filter"], index, batch_size)
        data["size"] = batch_size

    if wrong_range_filter_name:
        data["query"]["filter"] = []
        prepare_wrong_range_filter_name(data["query"]["filter"], index, batch_size)
        data["size"] = batch_size

    if wrong_term_filter_name:
        data["query"]["filter"] = []
        prepare_wrong_term_filter_name(data["query"]["filter"], index, batch_size)
        data["size"] = batch_size

    if wrong_vector:
        data["query"]["vector"] = []
        vector_info = {
            "field": "field_vector",
            "feature": features[:batch_size].flatten().tolist(),
        }
        data["query"]["vector"].append(vector_info)

    if wrong_length_document_ids:
        data["query"]["document_ids"] = [str(i) for i in range(max_document_ids_length)]

    if wrong_both_id_and_filter:
        data["query"]["document_ids"] = ["0"]
        data["query"]["filter"] = []
        prepare_filter(data["query"]["filter"], index, batch_size, 1, True)
        data["size"] = batch_size

    if empty_query:
        data["query"] = {}

    if empty_document_ids:
        data["query"]["document_ids"] = []

    if empty_filter:
        data["query"]["filter"] = []

    if out_of_bounds_ids:
        data["query"]["document_ids"] = [str(max_document_ids_length + 1)]
    json_str = json.dumps(data)

    if not wrong_vector:
        logger.info(json_str)
    try:
        rs = requests.post(url, data=json_str)
        logger.info(rs.json())
        if interface == "query":
            if "documents" not in rs.json():
                assert rs.status_code != 200
            else:
                if len(rs.json()["documents"]) > 0:
                    assert rs.json()["documents"][0]["status"] != 200
        else:
            if "document_ids" not in rs.json():
                assert rs.status_code != 200
            else:
                assert len(rs.json()["document_ids"]) == 0
    except Exception as e:
        logger.warning("exception: %s" % (repr(e)))


def query_error(logger, total, batch_size, xb, interface: str, wrong_parameters: list):
    for i in range(total):
        process_query_error_data(
            (
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                logger,
                interface,
                wrong_parameters,
            )
        )


def process_get_data(items):
    url = router_url + "/document/query"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["query"] = {}
    data["vector_value"] = True
    # data["fields"] = ["field_int"]

    logger = items[0]
    index = items[1]
    batch_size = items[2]
    features = items[3]
    full_field = items[4]
    seed = items[5]
    query_type = items[6]

    if query_type == "by_partition" or query_type == "by_partition_next" or query_type == "by_ids":
        data["query"]["document_ids"] = []
        if query_type == "by_partition_next" and batch_size > 1:
            batch_size -= 1
        for j in range(batch_size):
            data["query"]["document_ids"].append(str(index * batch_size + j))

    if query_type == "by_partition" or query_type == "by_partition_next":
        partition_id = "1"
        partition_ids = get_partition(router_url, db_name, space_name)
        if len(partition_ids) >= 1:
            partition_id = partition_ids[0]
        # logger.debug("partition_id: " + str(partition_id))
        data["query"]["partition_id"] = str(partition_id)
        if query_type == "by_partition_next":
            data["query"]["next"] = True

    if query_type == "by_filter":
        data["query"]["filter"] = []
        prepare_filter(data["query"]["filter"], index, batch_size, seed, full_field)
        data["size"] = batch_size

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)
    if rs.status_code != 200 or "documents" not in rs.json():
        logger.info(rs.json())
        logger.info(json_str)

    documents = rs.json()["documents"]
    if len(documents) != batch_size:
        logger.info("len(documents) = " + str(len(documents)))
        logger.info(json_str)

    assert len(documents) == batch_size
    assert rs.text.find('"total":' + str(batch_size)) >= 0

    for j in range(batch_size):
        value = int(documents[j]["_id"])
        if "_id" in documents[j]["_source"]:
            value = int(documents[j]["_source"]["_id"])
        logger.debug(value)
        logger.debug(documents[j])
        assert documents[j]["_source"]["field_int"] == value * seed
        if query_type == "by_ids":
            assert (
                documents[j]["_source"]["field_vector"]["feature"]
                == features[j].tolist()
            )
        if full_field:
            assert documents[j]["_source"]["field_long"] == value * seed
            assert documents[j]["_source"]["field_float"] == float(value * seed)
            assert documents[j]["_source"]["field_double"] == float(value * seed)


def query_interface(
    logger, total, batch_size, xb, full_field=False, seed=1, query_type="by_ids"
):
    if query_type == "by_partition_next" and batch_size == 1:
        total -= 1
    for i in range(total):
        process_get_data(
            (
                logger,
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                full_field,
                seed,
                query_type,
            )
        )


# def query_interface(logger, total, batch_size, xb, full_field=False, seed=1, query_type="by_ids"):
#     pool = ThreadPool()
#     total_data = []
#     for i in range(total):
#         total_data.append((logger, i, batch_size,  xb[i * batch_size: (i + 1) * batch_size], full_field, seed, query_type))
#     results = pool.map(process_get_data, total_data)
#     pool.close()
#     pool.join()


def process_delete_data(items):
    url = router_url + "/document/delete"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["query"] = {}

    logger = items[0]
    index = items[1]
    batch_size = items[2]
    full_field = items[3]
    seed = items[4]
    delete_type = items[5]

    if delete_type == "by_ids":
        data["query"]["document_ids"] = []
        for j in range(batch_size):
            data["query"]["document_ids"].append(str(index * batch_size + j))

    if delete_type == "by_filter":
        data["query"]["filter"] = []
        prepare_filter(data["query"]["filter"], index, batch_size, seed, full_field)
        data["size"] = batch_size

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)
    if rs.status_code != 200 or "document_ids" not in rs.json():
        logger.info(rs.json())
        logger.info(json_str)

    document_ids = rs.json()["document_ids"]
    if len(document_ids) != batch_size:
        logger.info(
            "batch_size = "
            + str(batch_size)
            + ", len(document_ids) = "
            + str(len(document_ids))
        )
        logger.info(json_str)
        logger.info(rs.json())
        logger.info(document_ids)

    assert len(document_ids) == batch_size
    assert rs.text.find('"total":' + str(batch_size)) >= 0


def delete_interface(
    logger, total, batch_size, full_field=False, seed=1, delete_type="by_ids"
):
    for i in range(total):
        process_delete_data((logger, i, batch_size, full_field, seed, delete_type))


def process_search_data(items):
    url = router_url + "/document/search"
    data = {}
    data["db_name"] = db_name
    data["space_name"] = space_name
    data["query"] = {}
    data["vector_value"] = True

    logger = items[0]
    index = items[1]
    batch_size = items[2]
    features = items[3]
    full_field = items[4]
    with_filter = items[5]
    seed = items[6]
    query_type = items[7]

    if query_type == "by_ids":
        data["query"]["document_ids"] = []
        for j in range(batch_size):
            data["query"]["document_ids"].append(str(index * batch_size + j))

    with_symbol = False
    if query_type == "by_vector_with_symbol":
        query_type = "by_vector"
        with_symbol = True


    if query_type == "by_vector":
        data["query"]["vector"] = []
        # logger.debug("partition_id: " + str(partition_id))
        vector_info = {
            "field": "field_vector",
            "feature": features[:batch_size].flatten().tolist(),
        }
        if with_symbol:
            vector_info["symbol"] = "<"
            vector_info["value"] = 40000
        data["query"]["vector"].append(vector_info)

    if with_filter:
        data["query"]["filter"] = []
        prepare_filter(data["query"]["filter"], index, batch_size, seed, full_field)

    json_str = json.dumps(data)
    rs = requests.post(url, json_str)
    if rs.status_code != 200 or "documents" not in rs.json():
        logger.info(rs.json())
        logger.info(json_str)

    documents = rs.json()["documents"]
    if len(documents) != batch_size:
        logger.info("len(documents) = " + str(len(documents)))
        logger.info(json_str)
        logger.info(rs.json())

    assert len(documents) == batch_size

    for j in range(batch_size):
        for document in documents[j]:
            value = int(document["_id"])
            logger.debug(value)
            logger.debug(document)
            assert document["_source"]["field_int"] == value * seed
            if full_field:
                assert document["_source"]["field_long"] == value * seed
                assert document["_source"]["field_float"] == float(value * seed)
                assert document["_source"]["field_double"] == float(value * seed)
            if with_symbol:
                assert document["_score"] < 40000


def search_interface(
    logger,
    total,
    batch_size,
    xb,
    full_field=False,
    with_filter=False,
    seed=1,
    query_type="by_ids",
):
    for i in range(total):
        process_search_data(
            (
                logger,
                i,
                batch_size,
                xb[i * batch_size : (i + 1) * batch_size],
                full_field,
                with_filter,
                seed,
                query_type,
            )
        )


def create_for_document_test(logger, router_url, embedding_size, properties):
    space_config = {
        "name": space_name,
        "partition_num": 1,
        "replica_num": 1,
        "index": {
            "index_name": "gamma",
            "index_type": "FLAT",
            "index_params": {
                "metric_type": "L2",
            },
        },
        "fields": properties["fields"],
    }
    logger.info(create_db(router_url, db_name))

    logger.info(create_space(router_url, db_name, space_config))


def prepare_cluster_for_document_test(logger, total, xb):
    embedding_size = xb.shape[1]
    batch_size = 100
    if total == 0:
        total = xb.shape[0]
    total_batch = int(total / batch_size)
    with_id = True
    full_field = True
    seed = 1

    properties = {}
    properties["fields"] = {
        "field_int": {"type": "integer", "index": True},
        "field_long": {"type": "long", "index": False},
        "field_float": {"type": "float", "index": False},
        "field_double": {"type": "double", "index": True},
        "field_string": {"type": "string", "index": True},
        "field_vector": {
            "type": "vector",
            "index": True,
            "dimension": embedding_size,
            "store_type": "MemoryOnly",
            # "format": "normalization"
        },
    }

    create_for_document_test(logger, router_url, embedding_size, properties)

    add(total_batch, batch_size, xb, with_id, full_field)

    time.sleep(3)

    query_interface(logger, total_batch, batch_size, xb, full_field, seed, "by_ids")


def waiting_index_finish(logger, total):
    url = router_url + "/cluster/health?db=" + db_name + "&space=" + space_name
    num = 0
    while num < total:
        response = requests.get(url)
        num = response.json()[0]["spaces"][0]["partitions"][0]["index_num"]
        logger.info("index num: %d" % (num))
        time.sleep(10)


def get_space_num():
    url = router_url + "/cluster/health?db=" + db_name + "&space=" + space_name
    num = 0
    response = requests.get(url)
    num = response.json()[0]["spaces"][0]["doc_num"]
    return num


def search(xq, k: int, batch: bool, query_dict: dict, logger):
    url = router_url + "/document/search?timeout=2000000"

    field_ints = []
    vector_dict = {"vector": [{"field": "field_vector", "feature": []}]}
    if batch:
        vector_dict["vector"][0]["feature"] = xq.flatten().tolist()
        query_dict["query"]["vector"] = vector_dict["vector"]
        json_str = json.dumps(query_dict)
        rs = requests.post(url, json_str)

        if rs.status_code != 200 or "documents" not in rs.json():
            logger.info(rs.json())
            logger.info(json_str)

        for results in rs.json()["documents"]:
            field_int = []
            for result in results:
                field_int.append(result["_source"]["field_int"])
            if len(field_int) != k:
                logger.debug("len(field_int)=" + str(len(field_int)))
                [field_int.append(-1) for i in range(k - len(field_int))]
            assert len(field_int) == k
            field_ints.append(field_int)
    else:
        for i in range(xq.shape[0]):
            vector_dict["vector"][0]["feature"] = xq[i].tolist()
            query_dict["query"]["vector"] = vector_dict["vector"]
            json_str = json.dumps(query_dict)
            rs = requests.post(url, json_str)

            if rs.status_code != 200 or "documents" not in rs.json():
                logger.info(rs.json())
                logger.info(json_str)

            field_int = []
            for results in rs.json()["documents"]:
                for result in results:
                    field_int.append(result["_source"]["field_int"])
            if len(field_int) != k:
                logger.debug("len(field_int)=" + str(len(field_int)))
                [field_int.append(-1) for i in range(k - len(field_int))]
            assert len(field_int) == k
            field_ints.append(field_int)
    assert len(field_ints) == xq.shape[0]
    return np.array(field_ints)


def evaluate(xq, gt, k, batch, query_dict, logger):
    nq = xq.shape[0]
    t0 = time.time()
    I = search(xq, k, batch, query_dict, logger)
    t1 = time.time()

    recalls = {}
    i = 1
    while i <= k:
        recalls[i] = (I[:, :i] == gt[:, :1]).sum() / float(nq)
        i *= 10

    return (t1 - t0) * 1000.0 / nq, recalls


def drop_db(router_url: str, db_name: str):
    url = f"{router_url}/dbs/{db_name}"
    resp = requests.delete(url)
    return resp.json()


def drop_space(router_url: str, db_name: str, space_name: str):
    url = f"{router_url}/dbs/{db_name}/spaces/{space_name}"
    resp = requests.delete(url)
    return resp.json()


def destroy(router_url: str, db_name: str, space_name: str):
    print(drop_space(router_url, db_name, space_name))
    print(drop_db(router_url, db_name))


def create_space(router_url: str, db_name: str, space_config: dict):
    url = f"{router_url}/dbs/{db_name}/spaces"
    resp = requests.post(url, json=space_config)
    return resp.json()


def get_space(router_url: str, db_name: str, space_name: str):
    url = f"{router_url}/dbs/{db_name}/spaces/{space_name}"
    resp = requests.get(url)
    return resp.json()


def get_partition(router_url: str, db_name: str, space_name: str):
    url = f"{router_url}/{db_name}/{space_name}"
    resp = requests.get(url)
    partition_infos = resp.json()["partitions"]
    partition_ids = []
    for partition_info in partition_infos:
        partition_ids.append(partition_info["id"])
    return partition_ids


def get_cluster_stats(router_url: str):
    url = f"{router_url}/cluster/stats"
    resp = requests.get(url)
    return resp.json()


def get_cluster_health(router_url: str):
    url = f"{router_url}/cluster/health"
    resp = requests.get(url)
    return resp.json()


def get_servers_status(router_url: str):
    url = f"{router_url}/list/server"
    resp = requests.get(url)
    return resp.json()


def list_dbs(router_url: str):
    url = f"{router_url}/dbs"
    resp = requests.get(url)
    return resp.json()


def create_db(router_url: str, db_name: str):
    url = f"{router_url}/dbs/" + db_name
    resp = requests.post(url)
    return resp.json()


def get_db(router_url: str, db_name: str):
    url = f"{router_url}/dbs/{db_name}"
    resp = requests.get(url)
    return resp.json()


def list_spaces(router_url: str, db_name: str):
    url = f"{router_url}/list/space?db={db_name}"
    resp = requests.get(url)
    return resp.json()

def describe_space(logger, router_url: str, db_name: str, space_name: str):
    url = f"{router_url}/dbs/{db_name}/spaces/{space_name}?detail=true"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        logger.error(e)

def index_rebuild(router_url: str, db_name: str, space_name: str):
    url = f"{router_url}/index/rebuild"
    data = {'db_name': db_name, 'space_name': space_name, 'drop_before_rebuild':True}
    resp = requests.post(url, json=data)
    return resp.json()