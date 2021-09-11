# -*- coding: utf-8 -*-
import explainaboard.error_analysis as ea
import explainaboard.data_utils as du
import os
import numpy


def process_all(file_path, size_of_bin=10, dataset='atis', model='lstm-self-attention'):
    """

    :param file_path: the file_path is the path to your file.

    And the path must include file name.

    the file name is in this format: test_dataset_model.tsv.

    the file_path must in the format: /root/path/to/your/file/test_dataset.tsv

    The file must in this format:
    sentence1\tsentence2\tground_truth\tpredict_label\tprobability\tright_or_not
    if prediction is right, right_or_not is assigned to 1, otherwise 0.

    :param size_of_bin: the numbers of how many bins

    :param dataset: the name of the dataset

    :param model: the name of the model

    :return:
    ece :the ece of this file
    dic :the details of the ECE information in json format
    """
    from collections import OrderedDict

    probability_list, right_or_not_list = du.get_probability_right_or_not(file_path, prob_col=4, right_or_not_col=5)

    raw_list = list(zip(probability_list, right_or_not_list))

    bin_list = ea.divide_into_bin(size_of_bin, raw_list)

    ece = ea.calculate_ece(bin_list)
    dic = OrderedDict()
    dic['dataset-name'] = dataset
    dic['model-name'] = model
    dic['ECE'] = ece
    dic['details'] = []
    basic_width = 1 / size_of_bin
    for i in range(len(bin_list)):
        tem_dic = {}
        bin_name = format(i * basic_width, '.2g') + '-' + format((i + 1) * basic_width, '.2g')
        tem_dic = {'interval': bin_name, 'average_accuracy': bin_list[i][1], 'average_confidence': bin_list[i][0],
                   'samples_number_in_this_bin': bin_list[i][2]}
        dic['details'].append(tem_dic)

    return ece, dic


def get_aspect_value(sent1_list, sent2_list, sample_list_tag, sample_list_tag_pred, dict_aspect_func):
    dict_span2aspect_val = {}
    dict_span2aspect_val_pred = {}

    for aspect, fun in dict_aspect_func.items():
        dict_span2aspect_val[aspect] = {}
        dict_span2aspect_val_pred[aspect] = {}

    # for error analysis
    dict_sid2sentpair = {}

    sample_id = 0
    for sent1, sent2, tag, tag_pred in zip(sent1_list, sent2_list, sample_list_tag, sample_list_tag_pred):

        word_list1 = ea.word_segment(sent1).split(" ")
        word_list2 = ea.word_segment(sent2).split(" ")

        # for saving errorlist -- fine-grained version
        dict_sid2sentpair[str(sample_id)] = ea.format4json2(
            ea.format4json2(sent1) + "|||" + ea.format4json2(sent2))

        sent1_length = len(word_list1)
        sent2_length = len(word_list2)

        sent_pos = ea.tuple2str((sample_id, tag))
        sent_pos_pred = ea.tuple2str((sample_id, tag_pred))

        hypo = [ea.word_segment(sent2)]
        refs = [[ea.word_segment(sent1)]]

        # bleu = sacrebleu.corpus_bleu(hypo, refs).score * 0.01

        # aspect = "bleu"
        # if aspect in dict_aspect_func.keys():
        # 	dict_span2aspect_val["bleu"][sent_pos] = bleu
        # 	dict_span2aspect_val_pred["bleu"][sent_pos_pred] = bleu

        # Sentence Length: sentALen
        aspect = "sentALen"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val[aspect][sent_pos] = float(sent1_length)
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = float(sent1_length)

        # Sentence Length: sentBLen
        aspect = "sentBLen"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val["sentBLen"][sent_pos] = float(sent2_length)
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = float(sent2_length)

        # The difference of sentence length: senDeltaLen
        aspect = "A-B"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val["A-B"][sent_pos] = float(sent1_length - sent2_length)
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = float(sent1_length - sent2_length)

        # "A+B"
        aspect = "A+B"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val["A+B"][sent_pos] = float(sent1_length + sent2_length)
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = float(sent1_length + sent2_length)

        # "A/B"
        aspect = "A/B"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val["A/B"][sent_pos] = float(sent1_length * 1.0 / sent2_length)
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = float(sent1_length * 1.0 / sent2_length)

        # Tag: tag
        aspect = "tag"
        if aspect in dict_aspect_func.keys():
            dict_span2aspect_val["tag"][sent_pos] = tag
            dict_span2aspect_val_pred[aspect][sent_pos_pred] = tag

        sample_id += 1
    # print(dict_span2aspect_val["bleu"])
    return dict_span2aspect_val, dict_span2aspect_val_pred, dict_sid2sentpair


def evaluate(task_type="ner", analysis_type="single", systems=[], output="./output.json", is_print_ci=False,
             is_print_case=False, is_print_ece=False):
    path_text = ""

    if analysis_type == "single":
        path_text = systems[0]

    corpus_type = "dataset_name"
    model_name = "model_name"
    path_precomputed = ""
    path_file = os.path.dirname(__file__)
    path_aspect_conf = os.path.join(path_file, "conf.aspects")
    path_json_input = os.path.join(path_file, "template.json")
    fn_write_json = output

    # Initalization
    dict_aspect_func = ea.load_conf(path_aspect_conf)
    metric_names = list(dict_aspect_func.keys())
    print("dict_aspect_func: ", dict_aspect_func)
    print(dict_aspect_func)

    fwrite_json = open(fn_write_json, 'w')

    # get precomputed paths from conf file
    dict_precomputed_path = {}
    for aspect, func in dict_aspect_func.items():
        is_precomputed = func[2].lower()
        if is_precomputed == "yes":
            dict_precomputed_path[aspect] = path_precomputed + "_" + aspect + ".pkl"
            print("precomputed directory:\t", dict_precomputed_path[aspect])

    sent1_list, sent2_list, true_label_list, pred_label_list = file_to_list(path_text)

    error_case_list = []
    if is_print_case:
        error_case_list = get_error_case(sent1_list, sent2_list, true_label_list, pred_label_list)
        print(" -*-*-*- the number of error casse:\t", len(error_case_list))

    # Confidence Interval of Holistic Performance
    confidence_low, confidence_up = 0, 0
    if is_print_ci:
        confidence_low, confidence_up = ea.compute_confidence_interval_acc(true_label_list, pred_label_list,
                                                                           n_times=100)

    dict_span2aspect_val, dict_span2aspect_val_pred, dict_sid2sentpair = get_aspect_value(sent1_list, sent2_list,
                                                                                      true_label_list, pred_label_list,
                                                                                      dict_aspect_func)

    holistic_performance = ea.accuracy(true_label_list, pred_label_list)
    holistic_performance = format(holistic_performance, '.3g')

    print("------------------ Holistic Result----------------------")
    print(holistic_performance)

    # print(f1(list_true_tags_token, list_pred_tags_token)["f1"])

    def __select_bucketing_func(func_name, func_setting, dict_obj):
        if func_name == "bucket_attribute_SpecifiedBucketInterval":
            return ea.bucket_attribute_specified_bucket_interval(dict_obj, eval(func_setting))
        elif func_name == "bucket_attribute_SpecifiedBucketValue":
            if len(func_setting.split("\t")) != 2:
                raise ValueError("selectBucktingFunc Error!")
            n_buckets, specified_bucket_value_list = int(func_setting.split("\t")[0]), eval(func_setting.split("\t")[1])
            return ea.bucket_attribute_specified_bucket_value(dict_obj, n_buckets, specified_bucket_value_list)
        elif func_name == "bucket_attribute_DiscreteValue":  # now the discrete value is R-tag..
            if len(func_setting.split("\t")) != 2:
                raise ValueError("selectBucktingFunc Error!")
            tags_list = list(set(dict_obj.values()))
            topK_buckets, min_buckets = int(func_setting.split("\t")[0]), int(func_setting.split("\t")[1])
            # return eval(func_name)(dict_obj, min_buckets, topK_buckets)
            return ea.bucket_attribute_discrete_value(dict_obj, topK_buckets, min_buckets)
        else:
            raise ValueError(f'Illegal function name {func_name}')

    dict_bucket2span = {}
    dict_bucket2span_pred = {}
    dict_bucket2f1 = {}
    aspect_names = []

    for aspect, func in dict_aspect_func.items():
        # print(aspect, dict_span2aspect_val[aspect])
        dict_bucket2span[aspect] = __select_bucketing_func(func[0], func[1], dict_span2aspect_val[aspect])
        # print(aspect, dict_bucket2span[aspect])
        # exit()
        dict_bucket2span_pred[aspect] = ea.bucket_attribute_specified_bucket_interval(dict_span2aspect_val_pred[aspect],
                                                                                      dict_bucket2span[aspect].keys())
        # dict_bucket2span_pred[aspect] = __select_bucketing_func(func[0], func[1], dict_span2aspect_val_pred[aspect])
        dict_bucket2f1[aspect] = get_bucket_acc_with_error_case(dict_bucket2span[aspect],
                                                                dict_bucket2span_pred[aspect], dict_sid2sentpair,
                                                                is_print_ci, is_print_case)
        aspect_names.append(aspect)
    print("aspect_names: ", aspect_names)

    print("------------------ Breakdown Performance")
    for aspect in dict_aspect_func.keys():
        ea.print_dict(dict_bucket2f1[aspect], aspect)
    print("")

    # Calculate databias w.r.t numeric attributes
    dict_aspect2bias = {}
    for aspect, aspect2Val in dict_span2aspect_val.items():
        if type(list(aspect2Val.values())[0]) != type("string"):
            dict_aspect2bias[aspect] = numpy.average(list(aspect2Val.values()))

    print("------------------ Dataset Bias")
    for k, v in dict_aspect2bias.items():
        print(k + ":\t" + str(v))
    print("")

    def beautify_interval(interval):

        if type(interval[0]) == type("string"):  ### pay attention to it
            return interval[0]
        else:
            if len(interval) == 1:
                bk_name = '(' + format(float(interval[0]), '.3g') + ',)'
                return bk_name
            else:
                range1_r = '(' + format(float(interval[0]), '.3g') + ','
                range1_l = format(float(interval[1]), '.3g') + ')'
                bk_name = range1_r + range1_l
                return bk_name

    dict_fine_grained = {}
    for aspect, metadata in dict_bucket2f1.items():
        dict_fine_grained[aspect] = []
        for bucket_name, v in metadata.items():
            # print("---------debug--bucket name old---")
            # print(bucket_name)
            bucket_name = beautify_interval(bucket_name)
            # print("---------debug--bucket name new---")
            # print(bucket_name)

            # bucket_value = format(v[0]*100,'.4g')
            bucket_value = format(v[0], '.4g')
            n_sample = v[1]
            confidence_low = format(v[2], '.4g')
            confidence_up = format(v[3], '.4g')

            # for saving errorlist -- fine_grained version
            bucket_error_case = v[4]

            # instantiation
            dict_fine_grained[aspect].append({"bucket_name": bucket_name, "bucket_value": bucket_value, "num": n_sample,
                                             "confidence_low": confidence_low, "confidence_up": confidence_up,
                                             "bucket_error_case": bucket_error_case})

    obj_json = ea.load_json(path_json_input)

    obj_json["task"] = task_type
    obj_json["data"]["name"] = corpus_type
    obj_json["data"]["language"] = "English"
    obj_json["data"]["bias"] = dict_aspect2bias

    obj_json["model"]["name"] = model_name
    obj_json["model"]["results"]["overall"]["performance"] = holistic_performance
    obj_json["model"]["results"]["overall"]["confidence_low"] = confidence_low
    obj_json["model"]["results"]["overall"]["confidence_up"] = confidence_up
    obj_json["model"]["results"]["fine_grained"] = dict_fine_grained

    # add errorAnalysis -- holistic
    obj_json["model"]["results"]["overall"]["error_case"] = error_case_list

    # for Calibration
    ece = 0
    dic_calibration = None
    if is_print_ece:
        ece, dic_calibration = process_all(path_text,
                                           size_of_bin=10, dataset=corpus_type, model=model_name)

    obj_json["model"]["results"]["calibration"] = dic_calibration

    ea.save_json(obj_json, fn_write_json)


def get_bucket_acc_with_error_case(dict_bucket2span, dict_bucket2span_pred, dict_sid2sentpair, is_print_ci,
                                   is_print_case):
    # The structure of span_true or span_pred
    # 2345|||Positive
    # 2345 represents sentence id
    # Positive represents the "label" of this instance

    dict_bucket2f1 = {}

    for bucket_interval, spans_true in dict_bucket2span.items():
        spans_pred = []
        if bucket_interval not in dict_bucket2span_pred.keys():
            raise ValueError("Predict Label Bucketing Errors")
        else:
            spans_pred = dict_bucket2span_pred[bucket_interval]

        # loop over samples from a given bucket
        error_case_bucket_list = []
        if is_print_case:
            for info_true, info_pred in zip(spans_true, spans_pred):
                sid_true, label_true = info_true.split("|||")
                sid_pred, label_pred = info_pred.split("|||")
                if sid_true != sid_pred:
                    continue

                sent = dict_sid2sentpair[sid_true]
                if label_true != label_pred:
                    error_case_info = label_true + "|||" + label_pred + "|||" + sent
                    error_case_bucket_list.append(error_case_info)

        accuracy_each_bucket = ea.accuracy(spans_pred, spans_true)
        confidence_low, confidence_up = 0, 0
        if is_print_ci:
            confidence_low, confidence_up = ea.compute_confidence_interval_acc(spans_pred, spans_true)
        dict_bucket2f1[bucket_interval] = [accuracy_each_bucket, len(spans_true), confidence_low, confidence_up,
                                           error_case_bucket_list]

    return ea.sort_dict(dict_bucket2f1)


def get_error_case(sent1_list, sent2_list, true_label_list, pred_label_list):
    error_case_list = []
    for sent1, sent2, true_label, pred_label in zip(sent1_list, sent2_list, true_label_list, pred_label_list):
        if true_label != pred_label:
            error_case_list.append(
                true_label + "|||" + pred_label + "|||" + ea.format4json2(sent1) + "|||" + ea.format4json2(sent2))
    return error_case_list


def file_to_list(path_file):
    sent1_list = []
    sent2_list = []
    true_label_list = []
    pred_label_list = []
    fin = open(path_file, "r")
    for line in fin:
        line = line.rstrip("\n")
        if len(line.split("\t")) < 4:
            continue
        sent1, sent2, true_label, pred_label = line.split("\t")[0], line.split("\t")[1], line.split("\t")[2], \
                                               line.split("\t")[3]
        sent1_list.append(sent1)
        sent2_list.append(sent2)
        true_label_list.append(true_label)
        pred_label_list.append(pred_label)

    fin.close()
    return sent1_list, sent2_list, true_label_list, pred_label_list