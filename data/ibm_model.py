"""
ibm_model.py | Author: Catherine Wong.

Utility script to run leave-N-out likelihood evaluations over paired language and program bitexts.

Usage: 
    python data/ibm_model.py
        --task_summaries dials_programs_all # TODO: make this an N+ later.
        --language_column lemmatized_whats
        --program_column dreamcoder_program_dsl_0
        --leave_out_n 1 # How many tasks to train/test on
        --random_likelihood_baseline # If provided, runs a sanity check fitting likelihoods.
"""
import random
import csv, os, json, argparse
import numpy as np
from nltk.translate import AlignedSent, IBMModel, IBMModel1

random.seed(0)
np.random.seed(0)

DEFAULT_DATA_DIR = "data"
DEFAULT_TRANSLATIONS_DIR = f"{DEFAULT_DATA_DIR}/translations"
DEFAULT_LANGUAGE_DIR = f"{DEFAULT_DATA_DIR}/language"
DEFAULT_PROGRAM_COLUMN = "dreamcoder_program_dsl_0_tokens"
LEMMATIZED_WHATS = "lemmatized_whats"
LEMMATIZED_WHATS_WHERES = "lemmatized_whats_wheres"
RAW_WHATS_WHERES = "raw_whats_wheres"
DEFAULT_LANGUAGE_COLUMN = LEMMATIZED_WHATS

PROGRAM_TOKENS, LANGUAGE_TOKENS = "program_tokens", "language_tokens"
TRANSLATION_MARGINAL_LOG_LIKELIHOODS = "translation_log_likelihoods"
RANDOM_TRANSLATION_MARGINAL_LOG_LIKELIHOODS = "random_translation_log_likelihoods"
DEFAULT_LEAVE_OUT_N = 2
DEFAULT_IBM_ITERATIONS = 5

parser = argparse.ArgumentParser()
parser.add_argument(
    "--export_dir",
    default=DEFAULT_TRANSLATIONS_DIR,
    help="If provided, alternate directory to export the translation results.",
)
parser.add_argument(
    "--task_summaries",
    required=True,
    help="Original CSV containing task summaries data.",
)
parser.add_argument(
    "--program_column",
    default=DEFAULT_PROGRAM_COLUMN,
    help="Column in the task summaries CSV containing the program.",
)
parser.add_argument(
    "--language_dir",
    default=DEFAULT_LANGUAGE_DIR,
    help="If provided, alternate directory to read in language data.",
)
parser.add_argument(
    "--language_column",
    default=DEFAULT_LANGUAGE_COLUMN,
    help="Column in the language CSV containing which language to use.",
)
parser.add_argument(
    "--leave_out_n",
    type=int,
    default=DEFAULT_LEAVE_OUT_N,
    help="How many tasks to leave out at each translation model fitting.",
)
parser.add_argument(
    "--num_ibm_iterations",
    type=int,
    default=DEFAULT_IBM_ITERATIONS,
)
parser.add_argument("--random_likelihood_baseline", action="store_true")


def get_task_to_tokens_dict(args):
    task_tokens_file = (
        f"{args.task_summaries}_{args.program_column}_{args.language_column}"
    )
    task_tokens_file = os.path.join(args.language_dir, task_tokens_file)
    with open(task_tokens_file) as f:
        task_to_tokens_dict = json.load(f)

    print(f"...Read in {len(task_to_tokens_dict)} tasks from {task_tokens_file}.")
    return task_to_tokens_dict


def build_train_heldout_bitexts(args, heldout_tasks, task_to_tokens_dict):
    from collections import defaultdict

    train_bitext, heldout_bitext = [], defaultdict(list)
    for task in task_to_tokens_dict:
        program_tokens = task_to_tokens_dict[task][PROGRAM_TOKENS]
        for language_tokens in task_to_tokens_dict[task][LANGUAGE_TOKENS]:
            aligned_sent = AlignedSent(program_tokens, language_tokens)
            if task in heldout_tasks:
                heldout_bitext[task].append(aligned_sent)
            else:
                train_bitext.append(aligned_sent)
    return train_bitext, heldout_bitext


def get_heldout_task_likelihoods(task_to_tokens_dict, ibm_model, heldout_bitexts):
    for task in heldout_bitexts:
        task_to_tokens_dict[task][TRANSLATION_MARGINAL_LOG_LIKELIHOODS] = []
        for sentence_pair in heldout_bitexts[task]:
            translation_marginal_likelihood = sum(
                [
                    v
                    for v in ibm_model.prob_all_alignments(
                        sentence_pair.words, sentence_pair.mots
                    ).values()
                ]
            )
            log_likelihood = np.log(translation_marginal_likelihood)
            task_to_tokens_dict[task][TRANSLATION_MARGINAL_LOG_LIKELIHOODS].append(
                log_likelihood
            )
    return task_to_tokens_dict


def run_random_bitext_baseline(task_to_tokens_dict, ibm_model, heldout_bitexts):
    for task in heldout_bitexts:
        task_to_tokens_dict[task][RANDOM_TRANSLATION_MARGINAL_LOG_LIKELIHOODS] = []
        for sentence_pair in heldout_bitexts[task]:
            # Pick another one to be the heldout.
            random_task = random.choice([t for t in heldout_bitexts if t != task])
            random_target = random.choice(heldout_bitexts[random_task])
            translation_marginal_likelihood = sum(
                [
                    v
                    for v in ibm_model.prob_all_alignments(
                        sentence_pair.words, random_target.mots
                    ).values()
                ]
            )
            log_likelihood = np.log(translation_marginal_likelihood)
            task_to_tokens_dict[task][
                RANDOM_TRANSLATION_MARGINAL_LOG_LIKELIHOODS
            ].append(log_likelihood)
    return task_to_tokens_dict


def run_all_leave_n_out(args, task_to_tokens_dict, print_every=10):
    # Sort task keys.
    task_keys = sorted(list(task_to_tokens_dict.keys()))
    num_splits = int(len(task_keys) / args.leave_out_n)
    heldout_splits = np.array_split(task_keys, num_splits)
    for idx, heldout_tasks in enumerate(heldout_splits):
        if idx % print_every == 0:
            print(f"...fitting on iteration {idx}/{len(heldout_splits)}")
        # Build the bitexts except for the n.
        train_bitext, heldout_bitext = build_train_heldout_bitexts(
            args, heldout_tasks, task_to_tokens_dict
        )

        # Fit the IBM model.
        ibm_model = IBMModel1(train_bitext, args.num_ibm_iterations)
        task_to_tokens_dict = get_heldout_task_likelihoods(
            task_to_tokens_dict, ibm_model, heldout_bitext
        )

        # Run on the random train-set alternative while we're at it.
        if args.random_likelihood_baseline:
            task_to_tokens_dict = run_random_bitext_baseline(
                task_to_tokens_dict, ibm_model, heldout_bitext
            )
    return task_to_tokens_dict, ibm_model


def build_summary_json(task_to_likelihoods_dict, ibm_model):
    import itertools

    translation_log_likelihoods = list(
        itertools.chain.from_iterable(
            [
                task_entry.get(TRANSLATION_MARGINAL_LOG_LIKELIHOODS, [])
                for task_entry in task_to_likelihoods_dict.values()
            ]
        )
    )
    random_log_likelihoods = list(
        itertools.chain.from_iterable(
            [
                task_entry.get(RANDOM_TRANSLATION_MARGINAL_LOG_LIKELIHOODS, [])
                for task_entry in task_to_likelihoods_dict.values()
            ]
        )
    )
    task_to_likelihoods_dict = {
        "translation_log_likelihoods_mean": np.mean(translation_log_likelihoods),
        "translation_log_likelihoods_std": np.std(translation_log_likelihoods),
        "random_log_likelihoods_mean": np.mean(random_log_likelihoods),
        "random_log_likelihoods_std": np.std(random_log_likelihoods),
        "sample_ibm_model": ibm_model.translation_table,
    }
    return task_to_likelihoods_dict


def export_task_to_likelihoods_summary(args, task_to_likelihoods_dict, ibm_model):
    # Export the likelihoods dict.
    task_translations_file_base = (
        f"ibm_1_{args.task_summaries}_{args.program_column}_{args.language_column}"
    )
    task_translations_file = os.path.join(
        args.export_dir, task_translations_file_base + ".json"
    )
    with open(task_translations_file, "w") as f:
        json.dump(task_to_likelihoods_dict, f)
    print(f"Wrote out likelihoods to: {task_translations_file}")

    # Export the summary text.
    task_translations_file = os.path.join(
        args.export_dir, task_translations_file_base + "_summary.json"
    )
    summary = build_summary_json(task_to_likelihoods_dict, ibm_model)
    with open(task_translations_file, "w") as f:
        json.dump(summary, f)
    print(f"Wrote out summary to: {task_translations_file}")


def main(args):
    task_to_tokens_dict = get_task_to_tokens_dict(args)
    task_to_likelihoods_dict, ibm_model = run_all_leave_n_out(args, task_to_tokens_dict)
    export_task_to_likelihoods_summary(args, task_to_likelihoods_dict, ibm_model)


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)